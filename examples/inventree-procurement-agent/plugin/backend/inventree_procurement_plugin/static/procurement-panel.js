function c(t) {
  return t !== null && typeof t == "object" && !Array.isArray(t) ? t : null;
}
function o(t) {
  return typeof t == "number" && Number.isSafeInteger(t) && t > 0 ? t : null;
}
function j(t) {
  return Array.isArray(t) ? t.filter((e) => o(e) !== null) : [];
}
function J(t) {
  return Array.isArray(t) ? t.filter((e) => typeof e == "string") : [];
}
function g(t) {
  return typeof t == "string" && /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(t) ? t : null;
}
function te(t) {
  if (!/^[1-9][0-9]*$/.test(t)) return null;
  const e = o(Number(t));
  return e !== null && e <= 2147483647 ? e : null;
}
function K(t) {
  const e = c(t);
  return !e || typeof e.id != "string" || typeof e.status != "string" || typeof e.updated_at != "string" || !Array.isArray(e.build_ids) || !e.build_ids.every((r) => o(r) !== null) ? null : e;
}
function ne(t) {
  const e = c(t);
  if (!e || !Array.isArray(e.tasks)) return null;
  const r = e.tasks.map(K);
  return r.every((l) => l !== null) ? r : null;
}
function G(t) {
  return K(c(t)?.task);
}
function re(t) {
  const e = c(t);
  if (!e || o(e.build_line_id) === null || o(e.build_id) === null || o(e.part_id) === null) return null;
  const r = c(e.source);
  return {
    build_line_id: o(e.build_line_id),
    build_id: o(e.build_id),
    part_id: o(e.part_id),
    required: g(e.required),
    consumed: g(e.consumed),
    allocated: g(e.allocated),
    outstanding: g(e.outstanding),
    source: r && typeof r.model == "string" && o(r.pk) !== null && typeof r.formula == "string" ? { model: r.model, pk: o(r.pk), fields: J(r.fields), formula: r.formula } : null
  };
}
function ie(t) {
  const e = c(t);
  if (!e || o(e.part_id) === null) return null;
  const r = c(e.available_stock), l = c(e.preliminary_shortage), s = c(r?.source), d = c(l?.source), m = c(r?.location_assumption);
  return {
    part_id: o(e.part_id),
    name: typeof e.name == "string" ? e.name : "待核实",
    ipn: typeof e.ipn == "string" ? e.ipn : "待核实",
    units: typeof e.units == "string" ? e.units : "待核实",
    build_line_ids: j(e.build_line_ids),
    selected_build_outstanding: g(e.selected_build_outstanding),
    available_stock: {
      value: g(r?.value),
      source: s && typeof s.model == "string" && typeof s.field == "string" && o(s.build_context_id) !== null ? {
        model: s.model,
        field: s.field,
        build_context_id: o(s.build_context_id),
        build_line_ids: j(s.build_line_ids)
      } : null,
      location_scope: typeof m?.scope == "string" ? m.scope : null,
      allocation_assumption: typeof r?.allocation_assumption == "string" ? r.allocation_assumption : null,
      warning: typeof r?.warning == "string" ? r.warning : null
    },
    preliminary_shortage: {
      value: g(l?.value),
      source: d && typeof d.formula == "string" ? { formula: d.formula, build_line_ids: j(d.build_line_ids) } : null,
      warning: typeof l?.warning == "string" ? l.warning : null
    }
  };
}
function ae(t) {
  const e = c(t), r = c(e?.preview), l = c(r?.build);
  if (!e || typeof e.task_id != "string" || typeof e.snapshot_digest != "string" || !r || r.schema_version !== 1 || !l || o(l.build_id) === null || !Array.isArray(r.lines) || !Array.isArray(r.parts)) return null;
  const s = r.lines.map(re), d = r.parts.map(ie);
  return s.some((m) => m === null) || d.some((m) => m === null) ? null : {
    task_id: e.task_id,
    snapshot_digest: e.snapshot_digest,
    analyzed_at: typeof e.analyzed_at == "string" ? e.analyzed_at : null,
    build: {
      build_id: o(l.build_id),
      reference: typeof l.reference == "string" ? l.reference : "待核实",
      source_pk: o(c(l.source)?.pk)
    },
    lines: s,
    parts: d,
    warnings: J(r.warnings)
  };
}
function A(t) {
  return t === null ? "待核实" : t;
}
function S(t) {
  const r = c(c(t)?.response)?.status;
  return r === 400 ? "请求格式有误，请检查生产单 ID。" : r === 401 ? "登录已失效，请重新登录后重试。" : r === 403 ? "没有读取生产单、物料或库存所需的权限。" : r === 404 ? "生产单或任务不存在，或当前用户无法访问。" : r === 409 ? "预览尚未生成，请稍后刷新。" : "请求失败，请检查连接后重试。";
}
const E = window.MantineCore.Alert, N = window.MantineCore.Badge, x = window.MantineCore.Button, y = window.MantineCore.Group, H = window.MantineCore.Loader, P = window.MantineCore.Paper, w = window.MantineCore.Stack, a = window.MantineCore.Text, le = window.MantineCore.TextInput, se = window.MantineCore.Title, n = window.React, h = "/plugin/inventree_procurement/";
function oe({ line: t }) {
  const e = [
    ["需求量", t.required],
    ["已消耗", t.consumed],
    ["已分配", t.allocated],
    ["未满足需求", t.outstanding]
  ];
  return /* @__PURE__ */ n.createElement(P, { withBorder: !0, p: "sm" }, /* @__PURE__ */ n.createElement(w, { gap: "xs" }, /* @__PURE__ */ n.createElement(a, { fw: 600 }, "BuildLine ", t.build_line_id, " · Part ", t.part_id), /* @__PURE__ */ n.createElement(y, { gap: "md" }, e.map(([r, l]) => /* @__PURE__ */ n.createElement(a, { key: r, size: "sm" }, r, "：", A(l)))), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "来源：", t.source ? `${t.source.model} #${t.source.pk}；${t.source.fields.join(", ")}` : "待核实"), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "计算：", t.source?.formula ?? "待核实")));
}
function ce({ part: t }) {
  const e = t.available_stock, r = t.preliminary_shortage;
  return /* @__PURE__ */ n.createElement(P, { withBorder: !0, p: "sm" }, /* @__PURE__ */ n.createElement(w, { gap: "xs" }, /* @__PURE__ */ n.createElement(a, { fw: 600 }, "Part ", t.part_id, " · ", t.name, " (", t.ipn, ")"), /* @__PURE__ */ n.createElement(a, { size: "sm" }, "关联 BuildLine：", t.build_line_ids.join(", ") || "待核实"), /* @__PURE__ */ n.createElement(y, { gap: "md" }, /* @__PURE__ */ n.createElement(a, { size: "sm" }, "选中生产单未满足需求：", A(t.selected_build_outstanding), " ", t.units), /* @__PURE__ */ n.createElement(a, { size: "sm" }, "可用库存：", A(e.value), " ", t.units), /* @__PURE__ */ n.createElement(a, { size: "sm" }, "初步缺口：", A(r.value), " ", t.units)), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "库存来源：", e.source ? `${e.source.model}.${e.source.field}；生产单 ${e.source.build_context_id}；BuildLine ${e.source.build_line_ids.join(", ")}` : "待核实"), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "位置范围：", e.location_scope ?? "待核实"), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "分配口径：", e.allocation_assumption ?? "待核实"), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "缺口依据：", r.source ? `${r.source.formula}；BuildLine ${r.source.build_line_ids.join(", ")}` : "待核实"), e.warning && /* @__PURE__ */ n.createElement(E, { color: "yellow" }, e.warning), r.warning && /* @__PURE__ */ n.createElement(E, { color: "yellow" }, r.warning)));
}
function ue({ preview: t }) {
  return /* @__PURE__ */ n.createElement(w, { gap: "sm" }, /* @__PURE__ */ n.createElement(a, { size: "sm" }, "生产单：", t.build.reference, "（ID ", t.build.build_id, "；来源 Build #", t.build.source_pk ?? "待核实", "）"), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "快照摘要：", t.snapshot_digest, " · 分析时间：", t.analyzed_at ?? "待核实"), t.warnings.map((e, r) => /* @__PURE__ */ n.createElement(E, { key: r, color: "yellow" }, e)), t.lines.length === 0 && /* @__PURE__ */ n.createElement(a, { size: "sm", c: "dimmed" }, "此任务暂无物料需求行。"), t.lines.map((e) => /* @__PURE__ */ n.createElement(oe, { key: e.build_line_id, line: e })), t.parts.length > 0 && /* @__PURE__ */ n.createElement(a, { fw: 600 }, "按 Part 汇总的库存与初步缺口（库存仅计一次）"), t.parts.map((e) => /* @__PURE__ */ n.createElement(ce, { key: e.part_id, part: e })));
}
function de({ context: t }) {
  const [e, r] = n.useState("checking"), [l, s] = n.useState("checking"), [d, m] = n.useState([]), [$, L] = n.useState(""), [O, R] = n.useState(!1), [D, p] = n.useState(null), [U, v] = n.useState(!1), [_, q] = n.useState(null), [B, k] = n.useState("idle"), [F, I] = n.useState(null), [Q, T] = n.useState(null), [V, W] = n.useState(0), [X, Y] = n.useState(0), M = n.useRef(!1);
  n.useEffect(() => {
    const i = new AbortController();
    return r("checking"), s("checking"), p(null), t.api.get(`${h}health/`, { signal: i.signal }).then(async ({ data: u }) => {
      if (i.signal.aborted) return;
      if (!(u !== null && typeof u == "object" && "status" in u && u.status === "ok")) {
        r("unavailable"), s("unavailable");
        return;
      }
      r("available");
      try {
        const f = await t.api.get(`${h}tasks/`, { signal: i.signal });
        if (i.signal.aborted) return;
        const C = ne(f.data);
        C === null ? s("unavailable") : (m(C), s("available"), v(!1));
      } catch (f) {
        i.signal.aborted || (s("unavailable"), p(S(f)));
      }
    }).catch((u) => {
      i.signal.aborted || (r("unavailable"), s("unavailable"), p(S(u)));
    }), () => i.abort();
  }, [t.api, V]), n.useEffect(() => {
    if (!_) {
      k("idle"), I(null);
      return;
    }
    const i = new AbortController();
    return k("checking"), I(null), T(null), t.api.get(
      `${h}tasks/${encodeURIComponent(_)}/preview/`,
      { signal: i.signal }
    ).then(({ data: u }) => {
      if (i.signal.aborted) return;
      const b = ae(u);
      b === null || b.task_id !== _ ? (k("unavailable"), T("预览响应格式无法识别，请核对插件版本。")) : (I(b), k("available"));
    }).catch((u) => {
      i.signal.aborted || (k("unavailable"), T(S(u)));
    }), () => i.abort();
  }, [t.api, _, X]);
  const z = te($);
  async function Z() {
    if (!(M.current || z === null || e !== "available" || l !== "available" || U)) {
      M.current = !0, R(!0), p(null);
      try {
        const i = await t.api.post(`${h}tasks/`, { build_ids: [z] }), u = G(i.data);
        if (u === null) {
          v(!0), p("任务可能已创建，但响应格式无法识别。请先刷新任务列表核对。");
          return;
        }
        const b = await t.api.get(`${h}tasks/${encodeURIComponent(u.id)}/`), f = G(b.data);
        if (f === null || f.id !== u.id) {
          v(!0), p("任务已创建，但回查结果无法核对。请刷新任务列表后再继续。");
          return;
        }
        m((C) => [f, ...C.filter((ee) => ee.id !== f.id)]), q(f.id), L("");
      } catch (i) {
        v(!0), p(`${S(i)} 请先刷新任务列表核对，勿重复提交。`);
      } finally {
        M.current = !1, R(!1);
      }
    }
  }
  return /* @__PURE__ */ n.createElement(P, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ n.createElement(w, { gap: "md" }, /* @__PURE__ */ n.createElement(y, { justify: "space-between", align: "start" }, /* @__PURE__ */ n.createElement("div", null, /* @__PURE__ */ n.createElement(se, { order: 3 }, "采购分析任务"), /* @__PURE__ */ n.createElement(a, { size: "sm", c: "dimmed" }, "只读预览；不会创建采购单或发起审批。")), /* @__PURE__ */ n.createElement(N, { color: e === "available" ? "green" : e === "checking" ? "gray" : "red" }, e === "available" ? "插件可用" : e === "checking" ? "检查中" : "插件不可用")), e === "checking" && /* @__PURE__ */ n.createElement(H, { size: "sm", "aria-label": "检查插件状态" }), e === "unavailable" && /* @__PURE__ */ n.createElement(E, { color: "yellow" }, "无法确认插件服务状态。"), /* @__PURE__ */ n.createElement(y, { align: "end" }, /* @__PURE__ */ n.createElement(
    le,
    {
      label: "生产单 ID",
      inputMode: "numeric",
      value: $,
      onChange: (i) => L(i.currentTarget.value),
      error: $ && z === null ? "请输入一个正整数 ID。" : void 0,
      placeholder: "例如 123"
    }
  ), /* @__PURE__ */ n.createElement(
    x,
    {
      onClick: Z,
      loading: O,
      disabled: z === null || e !== "available" || l !== "available" || U
    },
    "创建分析任务"
  )), D && /* @__PURE__ */ n.createElement(E, { color: "yellow" }, D), /* @__PURE__ */ n.createElement(w, { gap: "xs" }, /* @__PURE__ */ n.createElement(a, { fw: 600 }, "任务状态"), l === "checking" && /* @__PURE__ */ n.createElement(a, { size: "sm", c: "dimmed" }, "正在加载任务…"), l === "unavailable" && /* @__PURE__ */ n.createElement(a, { size: "sm", c: "dimmed" }, "任务列表不可用。"), l === "available" && d.length === 0 && /* @__PURE__ */ n.createElement(a, { size: "sm", c: "dimmed" }, "当前账户暂无任务。"), l === "available" && d.map((i) => /* @__PURE__ */ n.createElement(P, { key: i.id, withBorder: !0, p: "xs" }, /* @__PURE__ */ n.createElement(y, { justify: "space-between" }, /* @__PURE__ */ n.createElement(a, { size: "sm", fw: 600 }, i.id), /* @__PURE__ */ n.createElement(N, { variant: "light" }, i.status)), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "生产单 ID：", i.build_ids.join(", ") || "待核实", " · 更新于 ", i.updated_at), /* @__PURE__ */ n.createElement(x, { size: "xs", variant: "subtle", onClick: () => q(i.id) }, "查看只读预览")))), /* @__PURE__ */ n.createElement(w, { gap: "xs" }, /* @__PURE__ */ n.createElement(y, { justify: "space-between" }, /* @__PURE__ */ n.createElement(a, { fw: 600 }, "物料需求与库存预览"), _ && /* @__PURE__ */ n.createElement(x, { size: "xs", variant: "light", onClick: () => Y((i) => i + 1) }, "刷新预览")), !_ && /* @__PURE__ */ n.createElement(a, { size: "sm", c: "dimmed" }, "选择任务后读取预览。"), B === "checking" && /* @__PURE__ */ n.createElement(H, { size: "sm", "aria-label": "加载预览" }), B === "unavailable" && /* @__PURE__ */ n.createElement(E, { color: "yellow" }, Q), B === "available" && F && /* @__PURE__ */ n.createElement(ue, { preview: F })), /* @__PURE__ */ n.createElement(a, { size: "xs", c: "dimmed" }, "数据来源：插件任务、BuildLine 与 Part 只读接口。供应商报价和采购执行尚未接入。"), /* @__PURE__ */ n.createElement(x, { variant: "light", size: "xs", onClick: () => W((i) => i + 1) }, "刷新任务列表")));
}
function me(t) {
  return /* @__PURE__ */ n.createElement(de, { context: t });
}
export {
  me as RenderProcurementPanel
};
