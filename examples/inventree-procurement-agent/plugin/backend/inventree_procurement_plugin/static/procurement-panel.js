const E = window.MantineCore.Alert, g = window.MantineCore.Badge, k = window.MantineCore.Button, c = window.MantineCore.Group, y = window.MantineCore.Loader, p = window.MantineCore.Paper, o = window.MantineCore.Stack, r = window.MantineCore.Text, C = window.MantineCore.Title, e = window.React, T = "/plugin/inventree_procurement/health/", A = "/plugin/inventree_procurement/tasks/";
function z(a) {
  if (!a || typeof a != "object" || !("tasks" in a)) return null;
  const i = a.tasks;
  return !Array.isArray(i) || !i.every(
    (n) => n && typeof n.id == "string" && typeof n.status == "string" && Array.isArray(n.build_ids) && n.build_ids.every(Number.isInteger) && typeof n.updated_at == "string"
  ) ? null : i;
}
function S({ context: a }) {
  const [i, n] = e.useState("checking"), [s, l] = e.useState("checking"), [u, d] = e.useState([]), [b, h] = e.useState(0);
  e.useEffect(() => {
    const t = new AbortController();
    return n("checking"), l("checking"), d([]), a.api.get(T, { signal: t.signal }).then(async ({ data: f }) => {
      if (t.signal.aborted) return;
      if (f?.status !== "ok") {
        n("unavailable"), l("unavailable");
        return;
      }
      n("available");
      try {
        const v = await a.api.get(A, { signal: t.signal });
        if (t.signal.aborted) return;
        const m = z(v.data);
        m === null ? l("unavailable") : (d(m), l("available"));
      } catch {
        t.signal.aborted || l("unavailable");
      }
    }).catch(() => {
      t.signal.aborted || (n("unavailable"), l("unavailable"));
    }), () => t.abort();
  }, [a.api, b]);
  const w = i === "available" ? "Available" : i === "checking" ? "Checking" : "Unavailable";
  return /* @__PURE__ */ e.createElement(p, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ e.createElement(o, { gap: "md" }, /* @__PURE__ */ e.createElement(c, { justify: "space-between", align: "start" }, /* @__PURE__ */ e.createElement("div", null, /* @__PURE__ */ e.createElement(C, { order: 3 }, "Procurement tasks"), /* @__PURE__ */ e.createElement(r, { size: "sm", c: "dimmed" }, "Read-only integration preview")), /* @__PURE__ */ e.createElement(g, { color: i === "available" ? "green" : i === "checking" ? "gray" : "red" }, w)), i === "checking" && /* @__PURE__ */ e.createElement(y, { size: "sm", "aria-label": "Checking plugin health" }), i === "unavailable" && /* @__PURE__ */ e.createElement(E, { color: "yellow", title: "Plugin service unavailable" }, "Health could not be confirmed. Check the plugin endpoint and your access."), /* @__PURE__ */ e.createElement(o, { gap: 4 }, /* @__PURE__ */ e.createElement(r, { fw: 600 }, "Task status"), s === "checking" && /* @__PURE__ */ e.createElement(r, { size: "sm", c: "dimmed" }, "Loading owned tasks…"), s === "unavailable" && /* @__PURE__ */ e.createElement(r, { size: "sm", c: "dimmed" }, "Task list is unavailable."), s === "available" && u.length === 0 && /* @__PURE__ */ e.createElement(r, { size: "sm", c: "dimmed" }, "No tasks found for this account."), s === "available" && u.map((t) => /* @__PURE__ */ e.createElement(p, { key: t.id, withBorder: !0, p: "xs" }, /* @__PURE__ */ e.createElement(c, { justify: "space-between" }, /* @__PURE__ */ e.createElement(r, { size: "sm", fw: 600 }, t.id), /* @__PURE__ */ e.createElement(g, { variant: "light" }, t.status)), /* @__PURE__ */ e.createElement(r, { size: "xs", c: "dimmed" }, "Build IDs: ", t.build_ids.length ? t.build_ids.join(", ") : "none"), /* @__PURE__ */ e.createElement(r, { size: "xs", c: "dimmed" }, "Updated: ", t.updated_at)))), /* @__PURE__ */ e.createElement(o, { gap: 4 }, /* @__PURE__ */ e.createElement(r, { fw: 600 }, "Data sources"), /* @__PURE__ */ e.createElement(r, { size: "sm", c: "dimmed" }, "Task records: ", s === "available" ? "plugin task API" : "unavailable", ".", " ", "Build details, stock, supplier parts, and quote documents: not connected.")), /* @__PURE__ */ e.createElement(c, null, /* @__PURE__ */ e.createElement(k, { variant: "light", size: "xs", onClick: () => h((t) => t + 1) }, "Refresh health"))));
}
function M(a) {
  return /* @__PURE__ */ e.createElement(S, { context: a });
}
export {
  M as RenderProcurementPanel
};
