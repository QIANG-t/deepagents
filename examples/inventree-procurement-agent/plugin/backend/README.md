# InvenTree procurement plugin backend

This is an installable **integration spike** for the pinned InvenTree source reviewed in `../../docs/integration_spike.md`. It was installed and exercised in an isolated InvenTree instance: authenticated task reads, owner filtering, persistence after restart, and purchasing-page panel rendering were verified. It uses `AppMixin`, `UrlsMixin`, and `UserInterfaceMixin`. Approval and purchase writes are not exposed.

## Read-only interface

With plugin support and the URL mixin enabled, `SLUG = "inventree_procurement"` maps these routes under `/plugin/inventree_procurement/`:

| Method and path | Response | Access |
| --- | --- | --- |
| `GET health/` | `{"status":"ok","writes_enabled":false}` | Authenticated user; anonymous gets JSON 401. |
| `GET tasks/` | Up to 100 of the current user's task metadata, newest first | Authenticated owner only. |
| `GET tasks/<uuid>/` | One owned task's metadata | Authenticated owner; another user's ID returns 404. |

The routes all include a trailing slash. There is no task creation, approval, or purchase write route. Task metadata contains the task UUID, status, build IDs, and timestamps; it does not return plan contents or credentials. `ProcurementTask.check_user_permission` denies generic model access, while these views explicitly filter by owner. Login and owner filtering were verified in the isolated instance; purchase-role permissions have not been tested and are not enforced by these read-only views.

The optional panel uses `UserInterfaceMixin.get_ui_panels`. It is offered only to authenticated users on the InvenTree purchasing index (`target_model = "purchasing"`) and only when the bundled JavaScript file exists. Its source is `procurement-panel.js:RenderProcurementPanel`. The panel calls the read-only health and task endpoints and contains no purchase action. The plugin must have InvenTree's interface plugin setting enabled for the panel to appear.

## Package and asset layout

The Python package exposes the `inventree_plugins` entry point in `pyproject.toml`. Its Django app name is `inventree_procurement_plugin`. The `0001_initial` migration creates a UUID task table with owner, status, selected build IDs, two digests, and timestamps. No HTTP endpoint creates tasks; a trusted Django shell command can seed one for the persistence spike.

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

`0001_initial`, anonymous rejection, authenticated health, owner-only task reads, restart persistence, static collection, and purchasing-page rendering were verified in the isolated instance. See the exact results and setup in `../../docs/integration_spike.md`. The seeded Build ID is a placeholder, not a real production order. Non-GET behavior and `makemigrations --check --dry-run` still need running-instance verification.

## Offline verification

From this directory:

```bash
python3.11 -m unittest discover -s tests/unit_tests -v
python3.11 -m compileall -q inventree_procurement_plugin
```

The tests use Django stand-ins and do not test plugin discovery, migrations, static collection, browser rendering, or InvenTree authentication middleware.
