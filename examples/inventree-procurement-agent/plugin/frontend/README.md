# Read-only InvenTree procurement panel

This frontend module follows the InvenTree `UserInterfaceMixin` entrypoint described in the pinned InvenTree source (`docs/docs/plugins/frontend.md`, `mixins/ui.md`) and uses the same React and Mantine instances as the host UI. It is a minimal integration preview: it reads owned task metadata but does not permit approval, order creation, or any other purchase write.

## Backend contract

The backend must serve the built `dist/procurement-panel.js` as a plugin static file and register a panel source equivalent to:

```python
self.plugin_static_file('procurement-panel.js:RenderProcurementPanel')
```

The panel makes only these requests through the host's authenticated `context.api` Axios instance:

- `GET /plugin/inventree_procurement/health/`: HTTP 200 with JSON containing `{"status":"ok"}` means the plugin is reachable. A non-`ok` body or request failure displays **Unavailable**. This says nothing about purchase permissions.
- `GET /plugin/inventree_procurement/tasks/`: HTTP 200 with `{"tasks":[{"id":"<uuid>","status":"created","build_ids":[1],"updated_at":"<ISO 8601>"}]}` supplies owned task metadata. The panel validates this shape, shows returned statuses and build IDs, and reports an empty list honestly. It does not infer stock or quote readiness from a task status.

The `inventree_procurement` slug, paths, and response shapes match the backend under `../backend/inventree_procurement_plugin/`. The panel renders explicit placeholders for build details, stock, supplier parts, and quote documents. The asset is packaged in the backend wheel; registration and rendering were verified in an isolated InvenTree instance. See `../../docs/integration_spike.md`.

## Isolated build

From this directory:

```sh
npm ci
npm run build
```

React and Mantine versions match the pinned InvenTree frontend. The pinned source lists `@inventreedb/ui` 1.6.0, but npm did not publish that version at implementation time. This frontend uses the latest published 1.5.0 **for TypeScript types only**. The one context field used by the panel, `api: AxiosInstance`, was checked in both the published 1.5.0 declaration and pinned 1.6.0 source. No `@inventreedb/ui` runtime code is bundled. The Vite config externalizes React and Mantine to globals that the pinned InvenTree `src/frontend/src/main.tsx` assigns to `window`. The resulting ES module is copied from `dist/` into the backend package's `static/` directory. It loaded and rendered in the pinned isolated instance. The official plugin creator is the supported way to scaffold the full plugin package; this directory is only the frontend slice of that structure.
