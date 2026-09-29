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
- `GET /plugin/inventree_procurement/tasks/<uuid>/explanation/`: reads the saved explanation. HTTP 409 with `code: "explanation_unavailable"` means no explanation has been generated yet. The panel offers a manual refresh and checks that the returned digest matches the visible preview before displaying the text.
- `POST /plugin/inventree_procurement/tasks/<uuid>/explanation/`: an explicit click sends an empty body. A successful response contains `{"explanation":{"text":"...","model":"deepseek-flash","snapshot_digest":"...","generated_at":"<ISO 8601>","tool_calls":[{"name":"read_task_snapshot","status":"success","tool_call_id":"<nonempty ID>","result_sha256":"<64 lowercase hex digits>"}]}}`. The panel displays this separately below the deterministic facts, including the model, timestamp, digest, tool call ID, and result digest. It validates all four tool evidence fields, prevents duplicate clicks, and never retries generation automatically. A busy generation, changed snapshot, provider failure, or unavailable service appears as an error.
- `GET /plugin/inventree_procurement/tasks/<uuid>/quote/`: reads the single saved quote for the owned task. HTTP 409 with `code: "quote_unavailable"` enables the paste form. A successful response contains `{"quote":{...}}` with the linked SupplierPart ID, the saved plain text, SHA-256 digest, timestamp, model, extracted fields, comparison checks, and one `read_quote_snapshot` tool call. The form is shown only after the backend confirms no quote exists.
- `POST /plugin/inventree_procurement/tasks/<uuid>/quote/`: an explicit click sends `{"supplier_part_id":123,"text":"<anonymous plain text>"}`. The ID is a positive integer and the text is nonblank and at most 8 KiB in UTF-8. Each extracted field is either null or `{value,evidence,start,end}`; positions count Unicode code points and `end` is exclusive. The panel checks that every evidence span exactly matches the saved source text. Checks are rendered as `match`, `conflict`, or `unverified`, separate from the extracted values. It validates the successful `read_quote_snapshot` tool call ID and result hash, prevents duplicate clicks, and never retries automatically. After an uncertain POST, the user must refresh the saved result before submitting again. It does not allow replacing a saved quote.

The `inventree_procurement` slug, paths, and existing task response shapes were checked against `../backend/inventree_procurement_plugin/views.py`, `explanation.py`, `quote.py`, `facts.py`, and `decision_preview.py`. The panel displays backend warnings, separates line demand from Part-level shared stock, and labels the shortage as preliminary. The AI explanation and quote extraction are labeled as information for manual review, not purchase advice. The read-only decision preview lists review blockers and keeps order quantity and total unavailable. The create/preview flow, DeepSeek explanation, and pasted quote flow were browser-tested in an isolated InvenTree instance with a non-superuser procurement reader; see the [milestone 2](../../docs/milestone2_integration_validation.md), [milestone 3](../../docs/milestone3_deepseek_integration_validation.md), and [milestone 4](../../docs/milestone4_quote_eval_v1_report.zh-CN.md) records. The decision preview passed API integration and frontend build checks; see [milestone 6](../../docs/milestone6_decision_preview.zh-CN.md). The built asset must be copied into the backend package after each frontend build.

## Isolated build

From this directory:

```sh
npm ci
npm test
npm run build
```

React and Mantine versions match the pinned InvenTree frontend. The pinned source lists `@inventreedb/ui` 1.6.0, but npm did not publish that version at implementation time. This frontend uses published 1.5.0 **for TypeScript types only**. The `api: AxiosInstance` context field was checked in both the 1.5.0 declaration and pinned 1.6.0 source. No `@inventreedb/ui` runtime code is bundled. The Vite config externalizes React and Mantine to globals that the pinned InvenTree `src/frontend/src/main.tsx` assigns to `window`. The resulting ES module is copied from `dist/` into the backend package's `static/` directory. The official plugin creator is the supported way to scaffold the full plugin package; this directory is only the frontend slice of that structure.
