# Single-build procurement analysis panel

This frontend module follows the InvenTree `UserInterfaceMixin` entrypoint described in the pinned InvenTree source (`docs/docs/plugins/frontend.md`, `mixins/ui.md`) and uses the same React and Mantine instances as the host UI. The user enters one build ID and explicitly creates a persisted **analysis task**. All business facts are then read only. There is no approval, purchase order creation, or supplier order action.

## Backend contract

The backend must serve the built `dist/procurement-panel.js` as a plugin static file and register a panel source equivalent to:

```python
self.plugin_static_file('procurement-panel.js:RenderProcurementPanel')
```

The panel makes only these requests through the host's authenticated `context.api` Axios instance, which already supplies credentials and CSRF handling:

- `GET /plugin/inventree_procurement/health/`: HTTP 200 with JSON containing `{"status":"ok"}` means the plugin is reachable. A non-`ok` body or request failure displays **Unavailable**. This says nothing about purchase permissions.
- `GET /plugin/inventree_procurement/tasks/`: HTTP 200 with `{"tasks":[{"id":"<uuid>","status":"created","build_ids":[1],"updated_at":"<ISO 8601>"}]}` supplies owned task metadata. The panel validates this shape, shows returned statuses and build IDs, and reports an empty list honestly. It does not infer stock or quote readiness from a task status.
- `POST /plugin/inventree_procurement/tasks/`: JSON `{"build_ids":[123]}` with exactly one integer in `1..2147483647`. HTTP 201 returns `{"task":{...},"preview_url":"/plugin/inventree_procurement/tasks/<uuid>/preview/"}`. The create button is disabled during a request, and a synchronous lock prevents two clicks before React rerenders. After an uncertain result, creation stays disabled until the user refreshes the task list to check for an existing task.
- `GET /plugin/inventree_procurement/tasks/<uuid>/`: after a 201 response, the panel reads the owned task back and checks its ID before showing its preview. The response is `{"task":{...}}`.
- `GET /plugin/inventree_procurement/tasks/<uuid>/preview/`: the response wraps a persisted `preview` with `schema_version: 1`, one `build`, `lines`, `parts`, and `warnings`. Each line supplies BuildLine IDs and decimal strings for `required`, `consumed`, `allocated`, and `outstanding`. Each Part supplies a single scoped `available_stock` and `preliminary_shortage`, each with `value`, source, assumptions, and optional warning. A missing or unverified `value` is shown as **待核实**; the UI never computes a substitute number. The outer response also contains `task_id`, `snapshot_digest`, and `analyzed_at`.

The `inventree_procurement` slug, paths, and response shapes were checked against `../backend/inventree_procurement_plugin/views.py` and `facts.py`. The panel displays backend warnings, separates line demand from Part-level shared stock, and labels the shortage as preliminary. It does not request supplier quotes. The create/preview flow was browser-tested in an isolated InvenTree instance with a non-superuser read-only procurement role; see the [validation record](../../docs/milestone2_integration_validation.md). The built asset must be copied into the backend package after each frontend build.

## Isolated build

From this directory:

```sh
npm ci
npm test
npm run build
```

React and Mantine versions match the pinned InvenTree frontend. The pinned source lists `@inventreedb/ui` 1.6.0, but npm did not publish that version at implementation time. This frontend uses published 1.5.0 **for TypeScript types only**. The `api: AxiosInstance` context field was checked in both the 1.5.0 declaration and pinned 1.6.0 source. No `@inventreedb/ui` runtime code is bundled. The Vite config externalizes React and Mantine to globals that the pinned InvenTree `src/frontend/src/main.tsx` assigns to `window`. The resulting ES module is copied from `dist/` into the backend package's `static/` directory. The official plugin creator is the supported way to scaffold the full plugin package; this directory is only the frontend slice of that structure.
