# InvenTree procurement plugin backend

This is an installable **integration spike** for the pinned InvenTree source reviewed in `../../docs/integration_spike.md`. Task creation and factual preview were exercised through real HTTP and the browser in an isolated InvenTree instance; see the [milestone 2 validation record](../../docs/milestone2_integration_validation.md). The plugin uses `AppMixin`, `UrlsMixin`, and `UserInterfaceMixin`. Approval and purchase writes are not exposed.

## Task and preview interface

With plugin support and the URL mixin enabled, `SLUG = "inventree_procurement"` maps these routes under `/plugin/inventree_procurement/`:

| Method and path | Response | Access |
| --- | --- | --- |
| `GET health/` | `{"status":"ok","writes_enabled":false}` | Authenticated user; anonymous gets JSON 401. |
| `GET tasks/` | Up to 100 of the current user's task metadata, newest first | Authenticated user with Build, BuildLine, Part, and StockItem view permission. |
| `POST tasks/` | Creates one durable analysis task and returns 201 | Same view permissions; JSON body `{"build_ids":[<one positive integer>]}`. |
| `GET tasks/<uuid>/` | One owned task's metadata | Authenticated owner with current business view permissions; another user's ID returns 404. |
| `GET tasks/<uuid>/preview/` | The stored factual snapshot | Authenticated owner with current business view permissions; another user's ID returns 404. |

`health.writes_enabled = false` refers to procurement approval and order writes; creating an analysis task is enabled.

The routes all include a trailing slash. `POST tasks/` accepts only one build ID from 1 through 2,147,483,647 in this milestone; malformed JSON, extra fields, multiple IDs, booleans, and out-of-range IDs return 400. Anonymous users get 401; a missing business view permission returns 403 before Build/BuildLine/Part/StockItem data is queried; an absent Build returns 404. Task detail and preview look up the owner first, so another user's task UUID returns 404. A legacy task without a preview returns 409 from the preview endpoint. Task creation is the only new write: there is no approval, purchase-order, or line-item route. The outer task route checks authentication first; its authenticated POST branch calls a separately CSRF-protected helper. This preserves a 401 for anonymous POST while requiring a CSRF token for session-based creation.

The POST response is `{"task":{...},"preview_url":"/plugin/inventree_procurement/tasks/<uuid>/preview/"}`. Task metadata includes `id`, `status`, `build_ids`, `snapshot_digest`, `preview_available`, `analyzed_at`, `created_at`, and `updated_at`. The preview response is `{"task_id":"<uuid>","snapshot_digest":"<sha256>","analyzed_at":"<ISO time>","preview":{...}}`. The stored `preview` contains `schema_version`, `build`, `lines`, `parts`, and `warnings`. Every line has `build_line_id`, `build_id`, `part_id`, `required`, `consumed`, `allocated`, `outstanding`, and a model/field/formula source. Quantity values are Decimal strings. Every Part has `selected_build_outstanding`, `available_stock`, `preliminary_shortage`, line IDs, Part identity, and source. Availability and shortage each carry a `value` (Decimal string or `null`), `source` (object or `null`), and warning (string or `null`).

The snapshot uses `BuildLineSerializer.annotate_queryset(..., build=selected_build)` for `available_stock`. In the pinned source this subtracts sales and build allocations and limits stock to `Build.take_from` and descendant locations when configured. The plugin checks StockItem view permission before running that query. It uses the annotation **once per Part**, even if several BuildLines reference the same Part. Missing, invalid, or conflicting annotations yield `null` availability and shortage with a warning. The initial shortage is `max(sum(selected line outstanding) - one scoped available_stock, 0)`. It is only a preview: it excludes incoming supply, substitute parts, and optional/consumable rules, and cannot authorize a purchase. `BuildLine.allocated_quantity()` supplies the allocation quantity; `outstanding = max(quantity - consumed - allocated, 0)`. Each fact records its Build, BuildLine, or Part PK. A task stores the snapshot in the database so GET preview remains stable after restart; current permissions are rechecked before disclosing it. The read is a best-effort transaction snapshot, not a lock against concurrent inventory changes.

`ProcurementTask.check_user_permission` denies generic model access, while plugin views explicitly filter by owner. The isolated-instance checks verified business-role denial, CSRF enforcement, owner filtering, task creation, and preview reads.

The optional panel uses `UserInterfaceMixin.get_ui_panels`. It is offered only to authenticated users on the InvenTree purchasing index (`target_model = "purchasing"`) and only when the bundled JavaScript file exists. Its source is `procurement-panel.js:RenderProcurementPanel`. The panel calls health, task, and preview endpoints and can create an analysis task; it contains no purchase action. The plugin must have InvenTree's interface plugin setting enabled for the panel to appear. The host purchasing page requires `purchase_order.view` for a non-superuser to open it, in addition to the business read rights required by this plugin's API.

## Package and asset layout

The Python package exposes the `inventree_plugins` entry point in `pyproject.toml`. Its Django app name is `inventree_procurement_plugin`. Migration `0001_initial` creates a UUID task table; `0002_task_preview` adds the durable preview and analysis timestamp. Existing shell-seeded tasks remain readable and return 409 for preview until analyzed through a new task.

Build the frontend from `../frontend/`, then copy only its output into this package before building/installing the backend:

```bash
cd ../frontend
npm ci
npm run build
cd ../backend
cp ../frontend/dist/procurement-panel.js inventree_procurement_plugin/static/procurement-panel.js
python -m pip install -e .
```

The command assumes `python` is the intended InvenTree environment. The copied file is included as package data in wheel and source distributions. InvenTree copies files from the package's `static/` directory into `/static/plugins/inventree_procurement/` when plugin static collection runs. If the frontend build is absent, the backend health/task endpoints remain available and no panel is registered. The current frontend uses `@inventreedb/ui` 1.5.0 for types while the pinned InvenTree source lists 1.6.0; the panel was rendered in that pinned instance.

## Running-instance verification

Use an isolated InvenTree instance and database at the pinned commit. Enable custom plugins plus the App, URL, and interface mixins; install this package in the same Python environment; activate the plugin and restart the server and worker. From `inventree/src/backend/InvenTree/`, with that instance's configuration loaded:

```bash
python manage.py showmigrations inventree_procurement_plugin
python manage.py migrate inventree_procurement_plugin
python manage.py showmigrations inventree_procurement_plugin
```

`0001_initial`, anonymous rejection, authenticated health, owner-only task reads, restart persistence, static collection, and purchasing-page rendering were verified in the earlier isolated instance. The [milestone 2 record](../../docs/milestone2_integration_validation.md) verifies `0002_task_preview`, real HTTP task creation and preview, stock scoped by the selected Build, denial cases, browser rendering under a non-superuser read-only procurement role, and snapshot survival after restart. `makemigrations --check --dry-run` remains to be run in that instance.

## Offline verification

From this directory:

```bash
python3.11 -m unittest discover -s tests/unit_tests -v
python3.11 -m compileall -q inventree_procurement_plugin
```

The tests use Django stand-ins and do not test plugin discovery, migrations, static collection, browser rendering, or InvenTree authentication middleware.
