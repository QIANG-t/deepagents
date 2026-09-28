function u(t) {
  return t !== null && typeof t == "object" && !Array.isArray(t) ? t : null;
}
function m(t) {
  return typeof t == "number" && Number.isSafeInteger(t) && t > 0 ? t : null;
}
function N(t) {
  return Array.isArray(t) ? t.filter((e) => m(e) !== null) : [];
}
function Z(t) {
  return Array.isArray(t) ? t.filter((e) => typeof e == "string") : [];
}
function y(t) {
  return typeof t == "string" && /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(t) ? t : null;
}
function ce(t) {
  if (!/^[1-9][0-9]*$/.test(t)) return null;
  const e = m(Number(t));
  return e !== null && e <= 2147483647 ? e : null;
}
function ee(t) {
  const e = u(t);
  return !e || typeof e.id != "string" || typeof e.status != "string" || typeof e.updated_at != "string" || !Array.isArray(e.build_ids) || !e.build_ids.every((a) => m(a) !== null) ? null : e;
}
function ue(t) {
  const e = u(t);
  if (!e || !Array.isArray(e.tasks)) return null;
  const a = e.tasks.map(ee);
  return a.every((r) => r !== null) ? a : null;
}
function K(t) {
  return ee(u(t)?.task);
}
function de(t) {
  const e = u(t);
  if (!e || m(e.build_line_id) === null || m(e.build_id) === null || m(e.part_id) === null) return null;
  const a = u(e.source);
  return {
    build_line_id: m(e.build_line_id),
    build_id: m(e.build_id),
    part_id: m(e.part_id),
    required: y(e.required),
    consumed: y(e.consumed),
    allocated: y(e.allocated),
    outstanding: y(e.outstanding),
    source: a && typeof a.model == "string" && m(a.pk) !== null && typeof a.formula == "string" ? { model: a.model, pk: m(a.pk), fields: Z(a.fields), formula: a.formula } : null
  };
}
function me(t) {
  const e = u(t);
  if (!e || m(e.part_id) === null) return null;
  const a = u(e.available_stock), r = u(e.preliminary_shortage), o = u(a?.source), p = u(r?.source), f = u(a?.location_assumption);
  return {
    part_id: m(e.part_id),
    name: typeof e.name == "string" ? e.name : "待核实",
    ipn: typeof e.ipn == "string" ? e.ipn : "待核实",
    units: typeof e.units == "string" ? e.units : "待核实",
    build_line_ids: N(e.build_line_ids),
    selected_build_outstanding: y(e.selected_build_outstanding),
    available_stock: {
      value: y(a?.value),
      source: o && typeof o.model == "string" && typeof o.field == "string" && m(o.build_context_id) !== null ? {
        model: o.model,
        field: o.field,
        build_context_id: m(o.build_context_id),
        build_line_ids: N(o.build_line_ids)
      } : null,
      location_scope: typeof f?.scope == "string" ? f.scope : null,
      allocation_assumption: typeof a?.allocation_assumption == "string" ? a.allocation_assumption : null,
      warning: typeof a?.warning == "string" ? a.warning : null
    },
    preliminary_shortage: {
      value: y(r?.value),
      source: p && typeof p.formula == "string" ? { formula: p.formula, build_line_ids: N(p.build_line_ids) } : null,
      warning: typeof r?.warning == "string" ? r.warning : null
    }
  };
}
function pe(t) {
  const e = u(t), a = u(e?.preview), r = u(a?.build);
  if (!e || typeof e.task_id != "string" || typeof e.snapshot_digest != "string" || !a || a.schema_version !== 1 || !r || m(r.build_id) === null || !Array.isArray(a.lines) || !Array.isArray(a.parts)) return null;
  const o = a.lines.map(de), p = a.parts.map(me);
  return o.some((f) => f === null) || p.some((f) => f === null) ? null : {
    task_id: e.task_id,
    snapshot_digest: e.snapshot_digest,
    analyzed_at: typeof e.analyzed_at == "string" ? e.analyzed_at : null,
    build: {
      build_id: m(r.build_id),
      reference: typeof r.reference == "string" ? r.reference : "待核实",
      source_pk: m(u(r.source)?.pk)
    },
    lines: o,
    parts: p,
    warnings: Z(a.warnings)
  };
}
function D(t) {
  return t === null ? "待核实" : t;
}
function ge(t) {
  const e = u(u(t)?.explanation);
  if (!e || typeof e.text != "string" || !e.text.trim() || typeof e.model != "string" || !e.model.trim() || typeof e.snapshot_digest != "string" || !e.snapshot_digest || typeof e.generated_at != "string" || !e.generated_at || !Array.isArray(e.tool_calls) || e.tool_calls.length !== 1) return null;
  const a = e.tool_calls.map(u);
  return a.some((r) => !r || r.name !== "read_task_snapshot" || r.status !== "success" || typeof r.tool_call_id != "string" || !r.tool_call_id.trim() || typeof r.result_sha256 != "string" || !/^[a-f0-9]{64}$/.test(r.result_sha256)) ? null : {
    text: e.text,
    model: e.model,
    snapshot_digest: e.snapshot_digest,
    generated_at: e.generated_at,
    tool_calls: a.map((r) => ({
      name: r.name,
      status: r.status,
      tool_call_id: r.tool_call_id,
      result_sha256: r.result_sha256
    }))
  };
}
function fe(t, e) {
  return t.snapshot_digest === e;
}
function te(t) {
  const e = u(u(t)?.response)?.status;
  return typeof e == "number" ? e : null;
}
function W(t) {
  const e = u(u(u(t)?.response)?.data)?.code;
  return typeof e == "string" ? e : null;
}
function z(t) {
  const e = te(t);
  return e === 400 ? "请求格式有误，请检查生产单 ID。" : e === 401 ? "登录已失效，请重新登录后重试。" : e === 403 ? "没有读取生产单、物料或库存所需的权限。" : e === 404 ? "生产单或任务不存在，或当前用户无法访问。" : e === 409 ? "预览尚未生成，请稍后刷新。" : "请求失败，请检查连接后重试。";
}
const _e = window.MantineCore.Alert, O = window.MantineCore.Button, be = window.MantineCore.Group, Q = window.MantineCore.Loader, V = window.MantineCore.Paper, J = window.MantineCore.Stack, b = window.MantineCore.Text, Ee = window.MantineCore.Title, l = window.React;
function we({ context: t, taskId: e, snapshotDigest: a }) {
  const [r, o] = l.useState("checking"), [p, f] = l.useState(null), [A, E] = l.useState(null), [q, B] = l.useState(0), h = l.useRef(!1), _ = `/plugin/inventree_procurement/tasks/${encodeURIComponent(e)}/explanation/`;
  function $(s) {
    const d = ge(s);
    return d === null ? (E("解释响应格式无法识别，请核对插件版本。"), o("error"), !1) : fe(d, a) ? (f(d), o("available"), !0) : (E("解释引用的快照与当前预览不同，已停止展示。请刷新预览后核对。"), o("error"), !1);
  }
  l.useEffect(() => {
    const s = new AbortController();
    return o("checking"), f(null), E(null), t.api.get(_, { signal: s.signal }).then(({ data: d }) => {
      s.signal.aborted || $(d);
    }).catch((d) => {
      s.signal.aborted || (te(d) === 409 && W(d) === "explanation_unavailable" ? o("missing") : (E(W(d) === "preview_unavailable" ? "事实预览尚不可用，请先刷新预览。" : z(d)), o("error")));
    }), () => s.abort();
  }, [t.api, _, a, q]);
  async function k() {
    if (!(h.current || r === "generating" || r === "checking" || r === "available")) {
      h.current = !0, o("generating"), f(null), E(null);
      try {
        const s = await t.api.post(_);
        $(s.data);
      } catch (s) {
        const d = W(s);
        E(d === "explanation_busy" ? "另一项解释生成正在进行，请稍后刷新已保存解释。" : d === "snapshot_changed" ? "生成期间事实快照已改变，请刷新预览。" : d === "explanation_unavailable" ? "AI 解释服务目前不可用，请检查服务配置。" : d === "explanation_failed" ? "AI 解释生成失败，请稍后手动重试。" : `${z(s)} 请先刷新已保存解释，确认是否已经生成。`), o("error");
      } finally {
        h.current = !1;
      }
    }
  }
  return /* @__PURE__ */ l.createElement(V, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ l.createElement(J, { gap: "sm" }, /* @__PURE__ */ l.createElement(Ee, { order: 4 }, "AI 解释"), /* @__PURE__ */ l.createElement(b, { size: "sm", c: "dimmed" }, "这是对已保存事实快照的文字解释，不是采购建议；上方数量与库存仍以确定性预览为准。"), r === "checking" && /* @__PURE__ */ l.createElement(Q, { size: "sm", "aria-label": "读取已保存解释" }), r === "missing" && /* @__PURE__ */ l.createElement(b, { size: "sm", c: "dimmed" }, "此任务尚未生成 AI 解释。"), r === "generating" && /* @__PURE__ */ l.createElement(Q, { size: "sm", "aria-label": "生成 AI 解释" }), r === "error" && /* @__PURE__ */ l.createElement(_e, { color: "yellow" }, A), r === "available" && p && /* @__PURE__ */ l.createElement(J, { gap: "xs" }, /* @__PURE__ */ l.createElement(b, { size: "sm" }, "模型：", p.model), /* @__PURE__ */ l.createElement(b, { size: "sm" }, "生成时间：", p.generated_at), /* @__PURE__ */ l.createElement(b, { size: "xs", c: "dimmed" }, "关联快照：", p.snapshot_digest), /* @__PURE__ */ l.createElement(b, { size: "sm", style: { whiteSpace: "pre-wrap" } }, p.text), /* @__PURE__ */ l.createElement(b, { fw: 600, size: "sm" }, "实际工具调用证据"), p.tool_calls.map((s, d) => /* @__PURE__ */ l.createElement(V, { key: d, withBorder: !0, p: "xs" }, /* @__PURE__ */ l.createElement(J, { gap: 2 }, /* @__PURE__ */ l.createElement(b, { size: "xs" }, s.name, " · ", s.status), /* @__PURE__ */ l.createElement(b, { size: "xs", style: { overflowWrap: "anywhere" } }, "调用 ID：", s.tool_call_id), /* @__PURE__ */ l.createElement(b, { size: "xs", style: { overflowWrap: "anywhere" } }, "结果 SHA-256：", s.result_sha256))))), /* @__PURE__ */ l.createElement(be, null, /* @__PURE__ */ l.createElement(
    O,
    {
      onClick: k,
      loading: r === "generating",
      disabled: r === "checking" || r === "generating" || r === "available"
    },
    "生成 AI 解释"
  ), /* @__PURE__ */ l.createElement(
    O,
    {
      variant: "light",
      onClick: () => B((s) => s + 1),
      disabled: r === "generating"
    },
    "刷新已保存解释"
  ))));
}
const C = window.MantineCore.Alert, X = window.MantineCore.Badge, j = window.MantineCore.Button, x = window.MantineCore.Group, Y = window.MantineCore.Loader, U = window.MantineCore.Paper, S = window.MantineCore.Stack, c = window.MantineCore.Text, ye = window.MantineCore.TextInput, he = window.MantineCore.Title, n = window.React, P = "/plugin/inventree_procurement/";
function ke({ line: t }) {
  const e = [
    ["需求量", t.required],
    ["已消耗", t.consumed],
    ["已分配", t.allocated],
    ["未满足需求", t.outstanding]
  ];
  return /* @__PURE__ */ n.createElement(U, { withBorder: !0, p: "sm" }, /* @__PURE__ */ n.createElement(S, { gap: "xs" }, /* @__PURE__ */ n.createElement(c, { fw: 600 }, "BuildLine ", t.build_line_id, " · Part ", t.part_id), /* @__PURE__ */ n.createElement(x, { gap: "md" }, e.map(([a, r]) => /* @__PURE__ */ n.createElement(c, { key: a, size: "sm" }, a, "：", D(r)))), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "来源：", t.source ? `${t.source.model} #${t.source.pk}；${t.source.fields.join(", ")}` : "待核实"), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "计算：", t.source?.formula ?? "待核实")));
}
function ve({ part: t }) {
  const e = t.available_stock, a = t.preliminary_shortage;
  return /* @__PURE__ */ n.createElement(U, { withBorder: !0, p: "sm" }, /* @__PURE__ */ n.createElement(S, { gap: "xs" }, /* @__PURE__ */ n.createElement(c, { fw: 600 }, "Part ", t.part_id, " · ", t.name, " (", t.ipn, ")"), /* @__PURE__ */ n.createElement(c, { size: "sm" }, "关联 BuildLine：", t.build_line_ids.join(", ") || "待核实"), /* @__PURE__ */ n.createElement(x, { gap: "md" }, /* @__PURE__ */ n.createElement(c, { size: "sm" }, "选中生产单未满足需求：", D(t.selected_build_outstanding), " ", t.units), /* @__PURE__ */ n.createElement(c, { size: "sm" }, "可用库存：", D(e.value), " ", t.units), /* @__PURE__ */ n.createElement(c, { size: "sm" }, "初步缺口：", D(a.value), " ", t.units)), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "库存来源：", e.source ? `${e.source.model}.${e.source.field}；生产单 ${e.source.build_context_id}；BuildLine ${e.source.build_line_ids.join(", ")}` : "待核实"), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "位置范围：", e.location_scope ?? "待核实"), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "分配口径：", e.allocation_assumption ?? "待核实"), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "缺口依据：", a.source ? `${a.source.formula}；BuildLine ${a.source.build_line_ids.join(", ")}` : "待核实"), e.warning && /* @__PURE__ */ n.createElement(C, { color: "yellow" }, e.warning), a.warning && /* @__PURE__ */ n.createElement(C, { color: "yellow" }, a.warning)));
}
function ze({ preview: t }) {
  return /* @__PURE__ */ n.createElement(S, { gap: "sm" }, /* @__PURE__ */ n.createElement(c, { size: "sm" }, "生产单：", t.build.reference, "（ID ", t.build.build_id, "；来源 Build #", t.build.source_pk ?? "待核实", "）"), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "快照摘要：", t.snapshot_digest, " · 分析时间：", t.analyzed_at ?? "待核实"), t.warnings.map((e, a) => /* @__PURE__ */ n.createElement(C, { key: a, color: "yellow" }, e)), t.lines.length === 0 && /* @__PURE__ */ n.createElement(c, { size: "sm", c: "dimmed" }, "此任务暂无物料需求行。"), t.lines.map((e) => /* @__PURE__ */ n.createElement(ke, { key: e.build_line_id, line: e })), t.parts.length > 0 && /* @__PURE__ */ n.createElement(c, { fw: 600 }, "按 Part 汇总的库存与初步缺口（库存仅计一次）"), t.parts.map((e) => /* @__PURE__ */ n.createElement(ve, { key: e.part_id, part: e })));
}
function xe({ context: t }) {
  const [e, a] = n.useState("checking"), [r, o] = n.useState("checking"), [p, f] = n.useState([]), [A, E] = n.useState(""), [q, B] = n.useState(!1), [h, _] = n.useState(null), [$, k] = n.useState(!1), [s, d] = n.useState(null), [M, I] = n.useState("idle"), [T, G] = n.useState(null), [ne, F] = n.useState(null), [ae, re] = n.useState(0), [ie, se] = n.useState(0), H = n.useRef(!1);
  n.useEffect(() => {
    const i = new AbortController();
    return a("checking"), o("checking"), _(null), t.api.get(`${P}health/`, { signal: i.signal }).then(async ({ data: g }) => {
      if (i.signal.aborted) return;
      if (!(g !== null && typeof g == "object" && "status" in g && g.status === "ok")) {
        a("unavailable"), o("unavailable");
        return;
      }
      a("available");
      try {
        const w = await t.api.get(`${P}tasks/`, { signal: i.signal });
        if (i.signal.aborted) return;
        const L = ue(w.data);
        L === null ? o("unavailable") : (f(L), o("available"), k(!1));
      } catch (w) {
        i.signal.aborted || (o("unavailable"), _(z(w)));
      }
    }).catch((g) => {
      i.signal.aborted || (a("unavailable"), o("unavailable"), _(z(g)));
    }), () => i.abort();
  }, [t.api, ae]), n.useEffect(() => {
    if (!s) {
      I("idle"), G(null);
      return;
    }
    const i = new AbortController();
    return I("checking"), G(null), F(null), t.api.get(
      `${P}tasks/${encodeURIComponent(s)}/preview/`,
      { signal: i.signal }
    ).then(({ data: g }) => {
      if (i.signal.aborted) return;
      const v = pe(g);
      v === null || v.task_id !== s ? (I("unavailable"), F("预览响应格式无法识别，请核对插件版本。")) : (G(v), I("available"));
    }).catch((g) => {
      i.signal.aborted || (I("unavailable"), F(z(g)));
    }), () => i.abort();
  }, [t.api, s, ie]);
  const R = ce(A);
  async function le() {
    if (!(H.current || R === null || e !== "available" || r !== "available" || $)) {
      H.current = !0, B(!0), _(null);
      try {
        const i = await t.api.post(`${P}tasks/`, { build_ids: [R] }), g = K(i.data);
        if (g === null) {
          k(!0), _("任务可能已创建，但响应格式无法识别。请先刷新任务列表核对。");
          return;
        }
        const v = await t.api.get(`${P}tasks/${encodeURIComponent(g.id)}/`), w = K(v.data);
        if (w === null || w.id !== g.id) {
          k(!0), _("任务已创建，但回查结果无法核对。请刷新任务列表后再继续。");
          return;
        }
        f((L) => [w, ...L.filter((oe) => oe.id !== w.id)]), d(w.id), E("");
      } catch (i) {
        k(!0), _(`${z(i)} 请先刷新任务列表核对，勿重复提交。`);
      } finally {
        H.current = !1, B(!1);
      }
    }
  }
  return /* @__PURE__ */ n.createElement(U, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ n.createElement(S, { gap: "md" }, /* @__PURE__ */ n.createElement(x, { justify: "space-between", align: "start" }, /* @__PURE__ */ n.createElement("div", null, /* @__PURE__ */ n.createElement(he, { order: 3 }, "采购分析任务"), /* @__PURE__ */ n.createElement(c, { size: "sm", c: "dimmed" }, "只读预览；不会创建采购单或发起审批。")), /* @__PURE__ */ n.createElement(X, { color: e === "available" ? "green" : e === "checking" ? "gray" : "red" }, e === "available" ? "插件可用" : e === "checking" ? "检查中" : "插件不可用")), e === "checking" && /* @__PURE__ */ n.createElement(Y, { size: "sm", "aria-label": "检查插件状态" }), e === "unavailable" && /* @__PURE__ */ n.createElement(C, { color: "yellow" }, "无法确认插件服务状态。"), /* @__PURE__ */ n.createElement(x, { align: "end" }, /* @__PURE__ */ n.createElement(
    ye,
    {
      label: "生产单 ID",
      inputMode: "numeric",
      value: A,
      onChange: (i) => E(i.currentTarget.value),
      error: A && R === null ? "请输入一个正整数 ID。" : void 0,
      placeholder: "例如 123"
    }
  ), /* @__PURE__ */ n.createElement(
    j,
    {
      onClick: le,
      loading: q,
      disabled: R === null || e !== "available" || r !== "available" || $
    },
    "创建分析任务"
  )), h && /* @__PURE__ */ n.createElement(C, { color: "yellow" }, h), /* @__PURE__ */ n.createElement(S, { gap: "xs" }, /* @__PURE__ */ n.createElement(c, { fw: 600 }, "任务状态"), r === "checking" && /* @__PURE__ */ n.createElement(c, { size: "sm", c: "dimmed" }, "正在加载任务…"), r === "unavailable" && /* @__PURE__ */ n.createElement(c, { size: "sm", c: "dimmed" }, "任务列表不可用。"), r === "available" && p.length === 0 && /* @__PURE__ */ n.createElement(c, { size: "sm", c: "dimmed" }, "当前账户暂无任务。"), r === "available" && p.map((i) => /* @__PURE__ */ n.createElement(U, { key: i.id, withBorder: !0, p: "xs" }, /* @__PURE__ */ n.createElement(x, { justify: "space-between" }, /* @__PURE__ */ n.createElement(c, { size: "sm", fw: 600 }, i.id), /* @__PURE__ */ n.createElement(X, { variant: "light" }, i.status)), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "生产单 ID：", i.build_ids.join(", ") || "待核实", " · 更新于 ", i.updated_at), /* @__PURE__ */ n.createElement(j, { size: "xs", variant: "subtle", onClick: () => d(i.id) }, "查看只读预览")))), /* @__PURE__ */ n.createElement(S, { gap: "xs" }, /* @__PURE__ */ n.createElement(x, { justify: "space-between" }, /* @__PURE__ */ n.createElement(c, { fw: 600 }, "物料需求与库存预览"), s && /* @__PURE__ */ n.createElement(j, { size: "xs", variant: "light", onClick: () => se((i) => i + 1) }, "刷新预览")), !s && /* @__PURE__ */ n.createElement(c, { size: "sm", c: "dimmed" }, "选择任务后读取预览。"), M === "checking" && /* @__PURE__ */ n.createElement(Y, { size: "sm", "aria-label": "加载预览" }), M === "unavailable" && /* @__PURE__ */ n.createElement(C, { color: "yellow" }, ne), M === "available" && T && /* @__PURE__ */ n.createElement(ze, { preview: T }), M === "available" && T && s && /* @__PURE__ */ n.createElement(
    we,
    {
      key: s,
      context: t,
      taskId: s,
      snapshotDigest: T.snapshot_digest
    }
  )), /* @__PURE__ */ n.createElement(c, { size: "xs", c: "dimmed" }, "数据来源：插件任务、BuildLine 与 Part 只读接口。供应商报价和采购执行尚未接入。"), /* @__PURE__ */ n.createElement(j, { variant: "light", size: "xs", onClick: () => re((i) => i + 1) }, "刷新任务列表")));
}
function Ce(t) {
  return /* @__PURE__ */ n.createElement(xe, { context: t });
}
export {
  Ce as RenderProcurementPanel
};
