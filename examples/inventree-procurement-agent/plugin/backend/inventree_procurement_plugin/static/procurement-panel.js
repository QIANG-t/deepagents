const K = {
  supplier_name: "供应商名称",
  sku: "供应商料号",
  unit_price: "单价",
  currency: "币种",
  price_unit: "计价单位",
  pack_quantity: "包装数量",
  valid_until: "报价有效期",
  lead_time: "交期"
}, ee = 8192;
function u(t) {
  return t !== null && typeof t == "object" && !Array.isArray(t) ? t : null;
}
function g(t) {
  return typeof t == "number" && Number.isSafeInteger(t) && t > 0 ? t : null;
}
function V(t) {
  return Array.isArray(t) ? t.filter((e) => g(e) !== null) : [];
}
function de(t) {
  return Array.isArray(t) ? t.filter((e) => typeof e == "string") : [];
}
function M(t) {
  return typeof t == "string" && /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(t) ? t : null;
}
function me(t) {
  if (!/^[1-9][0-9]*$/.test(t)) return null;
  const e = g(Number(t));
  return e !== null && e <= 2147483647 ? e : null;
}
function ye(t) {
  return me(t);
}
function pe(t) {
  return new TextEncoder().encode(t).length;
}
function te(t) {
  return t.trim().length > 0 && pe(t) <= ee;
}
function fe(t) {
  const e = u(t);
  return !e || typeof e.id != "string" || typeof e.status != "string" || typeof e.updated_at != "string" || !Array.isArray(e.build_ids) || !e.build_ids.every((n) => g(n) !== null) ? null : e;
}
function he(t) {
  const e = u(t);
  if (!e || !Array.isArray(e.tasks)) return null;
  const n = e.tasks.map(fe);
  return n.every((a) => a !== null) ? n : null;
}
function re(t) {
  return fe(u(t)?.task);
}
function ve(t) {
  const e = u(t);
  if (!e || g(e.build_line_id) === null || g(e.build_id) === null || g(e.part_id) === null) return null;
  const n = u(e.source);
  return {
    build_line_id: g(e.build_line_id),
    build_id: g(e.build_id),
    part_id: g(e.part_id),
    required: M(e.required),
    consumed: M(e.consumed),
    allocated: M(e.allocated),
    outstanding: M(e.outstanding),
    source: n && typeof n.model == "string" && g(n.pk) !== null && typeof n.formula == "string" ? { model: n.model, pk: g(n.pk), fields: de(n.fields), formula: n.formula } : null
  };
}
function ke(t) {
  const e = u(t);
  if (!e || g(e.part_id) === null) return null;
  const n = u(e.available_stock), a = u(e.preliminary_shortage), o = u(n?.source), p = u(a?.source), i = u(n?.location_assumption);
  return {
    part_id: g(e.part_id),
    name: typeof e.name == "string" ? e.name : "待核实",
    ipn: typeof e.ipn == "string" ? e.ipn : "待核实",
    units: typeof e.units == "string" ? e.units : "待核实",
    build_line_ids: V(e.build_line_ids),
    selected_build_outstanding: M(e.selected_build_outstanding),
    available_stock: {
      value: M(n?.value),
      source: o && typeof o.model == "string" && typeof o.field == "string" && g(o.build_context_id) !== null ? {
        model: o.model,
        field: o.field,
        build_context_id: g(o.build_context_id),
        build_line_ids: V(o.build_line_ids)
      } : null,
      location_scope: typeof i?.scope == "string" ? i.scope : null,
      allocation_assumption: typeof n?.allocation_assumption == "string" ? n.allocation_assumption : null,
      warning: typeof n?.warning == "string" ? n.warning : null
    },
    preliminary_shortage: {
      value: M(a?.value),
      source: p && typeof p.formula == "string" ? { formula: p.formula, build_line_ids: V(p.build_line_ids) } : null,
      warning: typeof a?.warning == "string" ? a.warning : null
    }
  };
}
function xe(t) {
  const e = u(t), n = u(e?.preview), a = u(n?.build);
  if (!e || typeof e.task_id != "string" || typeof e.snapshot_digest != "string" || !n || n.schema_version !== 1 || !a || g(a.build_id) === null || !Array.isArray(n.lines) || !Array.isArray(n.parts)) return null;
  const o = n.lines.map(ve), p = n.parts.map(ke);
  return o.some((i) => i === null) || p.some((i) => i === null) ? null : {
    task_id: e.task_id,
    snapshot_digest: e.snapshot_digest,
    analyzed_at: typeof e.analyzed_at == "string" ? e.analyzed_at : null,
    build: {
      build_id: g(a.build_id),
      reference: typeof a.reference == "string" ? a.reference : "待核实",
      source_pk: g(u(a.source)?.pk)
    },
    lines: o,
    parts: p,
    warnings: de(n.warnings)
  };
}
function F(t) {
  return t === null ? "待核实" : t;
}
function Se(t) {
  const e = u(u(t)?.explanation);
  if (!e || typeof e.text != "string" || !e.text.trim() || typeof e.model != "string" || !e.model.trim() || typeof e.snapshot_digest != "string" || !e.snapshot_digest || typeof e.generated_at != "string" || !e.generated_at || !Array.isArray(e.tool_calls) || e.tool_calls.length !== 1) return null;
  const n = e.tool_calls.map(u);
  return n.some((a) => !a || a.name !== "read_task_snapshot" || a.status !== "success" || typeof a.tool_call_id != "string" || !a.tool_call_id.trim() || typeof a.result_sha256 != "string" || !/^[a-f0-9]{64}$/.test(a.result_sha256)) ? null : {
    text: e.text,
    model: e.model,
    snapshot_digest: e.snapshot_digest,
    generated_at: e.generated_at,
    tool_calls: n.map((a) => ({
      name: a.name,
      status: a.status,
      tool_call_id: a.tool_call_id,
      result_sha256: a.result_sha256
    }))
  };
}
function ze(t, e) {
  return t.snapshot_digest === e;
}
function Ce(t, e) {
  if (t === null) return null;
  const n = u(t);
  if (!(!n || typeof n.value != "string" || !n.value.trim() || typeof n.evidence != "string" || !n.evidence.trim() || typeof n.start != "number" || !Number.isSafeInteger(n.start) || n.start < 0 || typeof n.end != "number" || !Number.isSafeInteger(n.end) || n.end <= n.start || Array.from(e).slice(n.start, n.end).join("") !== n.evidence))
    return { value: n.value, evidence: n.evidence, start: n.start, end: n.end };
}
function $e(t) {
  const e = u(u(t)?.quote), n = u(e?.extracted);
  if (!e || g(e.supplier_part_id) === null || typeof e.source_sha256 != "string" || !/^[a-f0-9]{64}$/.test(e.source_sha256) || typeof e.source_text != "string" || !te(e.source_text) || typeof e.created_at != "string" || !e.created_at.trim() || typeof e.model != "string" || !e.model.trim() || !n || !Array.isArray(e.checks) || !Array.isArray(e.tool_calls) || e.tool_calls.length !== 1) return null;
  const a = {};
  for (const i of Object.keys(K)) {
    const b = Ce(n[i], e.source_text);
    if (b === void 0) return null;
    a[i] = b;
  }
  const o = e.checks.map(u);
  if (o.some((i) => !i || typeof i.field != "string" || !i.field.trim() || !["match", "conflict", "unverified"].includes(i.status) || typeof i.message != "string" || !i.message.trim())) return null;
  const p = e.tool_calls.map(u);
  return p.some((i) => !i || i.name !== "read_quote_snapshot" || i.status !== "success" || typeof i.tool_call_id != "string" || !i.tool_call_id.trim() || typeof i.result_sha256 != "string" || !/^[a-f0-9]{64}$/.test(i.result_sha256)) ? null : {
    supplier_part_id: e.supplier_part_id,
    source_sha256: e.source_sha256,
    source_text: e.source_text,
    created_at: e.created_at,
    model: e.model,
    extracted: a,
    checks: o.map((i) => ({
      field: i.field,
      status: i.status,
      message: i.message
    })),
    tool_calls: p.map((i) => ({
      name: "read_quote_snapshot",
      status: "success",
      tool_call_id: i.tool_call_id,
      result_sha256: i.result_sha256
    }))
  };
}
function ne(t) {
  const e = u(u(t)?.response)?.status;
  return typeof e == "number" ? e : null;
}
function W(t) {
  const e = u(u(u(t)?.response)?.data)?.code;
  return typeof e == "string" ? e : null;
}
function T(t) {
  const e = ne(t);
  return e === 400 ? "请求格式有误，请检查生产单 ID。" : e === 401 ? "登录已失效，请重新登录后重试。" : e === 403 ? "没有读取生产单、物料或库存所需的权限。" : e === 404 ? "生产单或任务不存在，或当前用户无法访问。" : e === 409 ? "预览尚未生成，请稍后刷新。" : "请求失败，请检查连接后重试。";
}
const Ae = window.MantineCore.Alert, ae = window.MantineCore.Button, Ie = window.MantineCore.Group, se = window.MantineCore.Loader, ie = window.MantineCore.Paper, Z = window.MantineCore.Stack, z = window.MantineCore.Text, Te = window.MantineCore.Title, d = window.React;
function Be({ context: t, taskId: e, snapshotDigest: n }) {
  const [a, o] = d.useState("checking"), [p, i] = d.useState(null), [b, h] = d.useState(null), [D, k] = d.useState(0), C = d.useRef(!1), v = `/plugin/inventree_procurement/tasks/${encodeURIComponent(e)}/explanation/`;
  function B(l) {
    const f = Se(l);
    return f === null ? (h("解释响应格式无法识别，请核对插件版本。"), o("error"), !1) : ze(f, n) ? (i(f), o("available"), !0) : (h("解释引用的快照与当前预览不同，已停止展示。请刷新预览后核对。"), o("error"), !1);
  }
  d.useEffect(() => {
    const l = new AbortController();
    return o("checking"), i(null), h(null), t.api.get(v, { signal: l.signal }).then(({ data: f }) => {
      l.signal.aborted || B(f);
    }).catch((f) => {
      l.signal.aborted || (ne(f) === 409 && W(f) === "explanation_unavailable" ? o("missing") : (h(W(f) === "preview_unavailable" ? "事实预览尚不可用，请先刷新预览。" : T(f)), o("error")));
    }), () => l.abort();
  }, [t.api, v, n, D]);
  async function S() {
    if (!(C.current || a === "generating" || a === "checking" || a === "available")) {
      C.current = !0, o("generating"), i(null), h(null);
      try {
        const l = await t.api.post(v);
        B(l.data);
      } catch (l) {
        const f = W(l);
        h(f === "explanation_busy" ? "另一项解释生成正在进行，请稍后刷新已保存解释。" : f === "snapshot_changed" ? "生成期间事实快照已改变，请刷新预览。" : f === "explanation_unavailable" ? "AI 解释服务目前不可用，请检查服务配置。" : f === "explanation_failed" ? "AI 解释生成失败，请稍后手动重试。" : `${T(l)} 请先刷新已保存解释，确认是否已经生成。`), o("error");
      } finally {
        C.current = !1;
      }
    }
  }
  return /* @__PURE__ */ d.createElement(ie, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ d.createElement(Z, { gap: "sm" }, /* @__PURE__ */ d.createElement(Te, { order: 4 }, "AI 解释"), /* @__PURE__ */ d.createElement(z, { size: "sm", c: "dimmed" }, "这是对已保存事实快照的文字解释，不是采购建议；上方数量与库存仍以确定性预览为准。"), a === "checking" && /* @__PURE__ */ d.createElement(se, { size: "sm", "aria-label": "读取已保存解释" }), a === "missing" && /* @__PURE__ */ d.createElement(z, { size: "sm", c: "dimmed" }, "此任务尚未生成 AI 解释。"), a === "generating" && /* @__PURE__ */ d.createElement(se, { size: "sm", "aria-label": "生成 AI 解释" }), a === "error" && /* @__PURE__ */ d.createElement(Ae, { color: "yellow" }, b), a === "available" && p && /* @__PURE__ */ d.createElement(Z, { gap: "xs" }, /* @__PURE__ */ d.createElement(z, { size: "sm" }, "模型：", p.model), /* @__PURE__ */ d.createElement(z, { size: "sm" }, "生成时间：", p.generated_at), /* @__PURE__ */ d.createElement(z, { size: "xs", c: "dimmed" }, "关联快照：", p.snapshot_digest), /* @__PURE__ */ d.createElement(z, { size: "sm", style: { whiteSpace: "pre-wrap" } }, p.text), /* @__PURE__ */ d.createElement(z, { fw: 600, size: "sm" }, "实际工具调用证据"), p.tool_calls.map((l, f) => /* @__PURE__ */ d.createElement(ie, { key: f, withBorder: !0, p: "xs" }, /* @__PURE__ */ d.createElement(Z, { gap: 2 }, /* @__PURE__ */ d.createElement(z, { size: "xs" }, l.name, " · ", l.status), /* @__PURE__ */ d.createElement(z, { size: "xs", style: { overflowWrap: "anywhere" } }, "调用 ID：", l.tool_call_id), /* @__PURE__ */ d.createElement(z, { size: "xs", style: { overflowWrap: "anywhere" } }, "结果 SHA-256：", l.result_sha256))))), /* @__PURE__ */ d.createElement(Ie, null, /* @__PURE__ */ d.createElement(
    ae,
    {
      onClick: S,
      loading: a === "generating",
      disabled: a === "checking" || a === "generating" || a === "available"
    },
    "生成 AI 解释"
  ), /* @__PURE__ */ d.createElement(
    ae,
    {
      variant: "light",
      onClick: () => k((l) => l + 1),
      disabled: a === "generating"
    },
    "刷新已保存解释"
  ))));
}
const Me = window.MantineCore.Alert, Pe = window.MantineCore.Badge, le = window.MantineCore.Button, Le = window.MantineCore.Group, oe = window.MantineCore.Loader, N = window.MantineCore.Paper, X = window.MantineCore.Stack, w = window.MantineCore.Text, Re = window.MantineCore.Textarea, je = window.MantineCore.TextInput, De = window.MantineCore.Title, s = window.React, qe = Object.keys(K), Ue = { match: "匹配", conflict: "冲突", unverified: "待核实" }, Qe = { match: "green", conflict: "red", unverified: "yellow" };
function We({ quote: t }) {
  return /* @__PURE__ */ s.createElement(X, { gap: "sm" }, /* @__PURE__ */ s.createElement(w, { size: "sm" }, "关联 SupplierPart ID：", t.supplier_part_id), /* @__PURE__ */ s.createElement(w, { size: "sm" }, "模型：", t.model, " · 提取时间：", t.created_at), /* @__PURE__ */ s.createElement(w, { size: "xs", c: "dimmed", style: { overflowWrap: "anywhere" } }, "原文 SHA-256：", t.source_sha256), /* @__PURE__ */ s.createElement("details", null, /* @__PURE__ */ s.createElement("summary", null, "查看已保存的报价原文"), /* @__PURE__ */ s.createElement(w, { size: "sm", style: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" } }, t.source_text)), /* @__PURE__ */ s.createElement(w, { fw: 600, size: "sm" }, "抽取字段与原文证据"), qe.map((e) => {
    const n = t.extracted[e];
    return /* @__PURE__ */ s.createElement(N, { key: e, withBorder: !0, p: "xs" }, /* @__PURE__ */ s.createElement(w, { size: "sm", fw: 600 }, K[e], "：", n?.value ?? "待核实"), n && /* @__PURE__ */ s.createElement(w, { size: "xs", style: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" } }, "原文片段：", n.evidence, "（字符位置 ", n.start, "–", n.end, "，结束位置不含）"));
  }), /* @__PURE__ */ s.createElement(w, { fw: 600, size: "sm" }, "对照检查"), t.checks.length === 0 && /* @__PURE__ */ s.createElement(w, { size: "sm", c: "dimmed" }, "暂无可核对的字段。"), t.checks.map((e, n) => /* @__PURE__ */ s.createElement(N, { key: n, withBorder: !0, p: "xs" }, /* @__PURE__ */ s.createElement(Le, { gap: "xs" }, /* @__PURE__ */ s.createElement(Pe, { color: Qe[e.status] }, Ue[e.status]), /* @__PURE__ */ s.createElement(w, { size: "sm", fw: 600 }, e.field === "price_break" ? "价格阶梯对照" : K[e.field] ?? e.field)), /* @__PURE__ */ s.createElement(w, { size: "sm" }, e.message))), /* @__PURE__ */ s.createElement(w, { fw: 600, size: "sm" }, "实际工具调用证据"), t.tool_calls.map((e) => /* @__PURE__ */ s.createElement(N, { key: e.tool_call_id, withBorder: !0, p: "xs" }, /* @__PURE__ */ s.createElement(X, { gap: 2 }, /* @__PURE__ */ s.createElement(w, { size: "xs" }, e.name, " · ", e.status), /* @__PURE__ */ s.createElement(w, { size: "xs", style: { overflowWrap: "anywhere" } }, "调用 ID：", e.tool_call_id), /* @__PURE__ */ s.createElement(w, { size: "xs", style: { overflowWrap: "anywhere" } }, "结果 SHA-256：", e.result_sha256)))));
}
function Ge({ context: t, taskId: e }) {
  const [n, a] = s.useState("checking"), [o, p] = s.useState(null), [i, b] = s.useState(null), [h, D] = s.useState(""), [k, C] = s.useState(""), [v, B] = s.useState(0), S = s.useRef(!1), l = `/plugin/inventree_procurement/tasks/${encodeURIComponent(e)}/quote/`;
  function f(_, E) {
    const U = $e(_);
    return !U || E && U.supplier_part_id !== E ? (b("报价结果格式或关联 SupplierPart 无法核对，请刷新已保存结果。"), a("error"), !1) : (p(U), a("available"), !0);
  }
  s.useEffect(() => {
    const _ = new AbortController();
    return a("checking"), p(null), b(null), t.api.get(l, { signal: _.signal }).then(({ data: E }) => {
      _.signal.aborted || f(E);
    }).catch((E) => {
      _.signal.aborted || (ne(E) === 409 && W(E) === "quote_unavailable" ? a("missing") : (b(T(E)), a("error")));
    }), () => _.abort();
  }, [t.api, l, v]);
  const x = ye(h), A = pe(k), I = n === "missing" && x !== null && te(k);
  async function q() {
    if (!(S.current || !I || x === null)) {
      S.current = !0, a("submitting"), b(null);
      try {
        const _ = await t.api.post(l, { supplier_part_id: x, text: k });
        f(_.data, x) && C("");
      } catch (_) {
        const E = W(_);
        b(E === "quote_immutable" ? "此任务已保存另一份报价原文。请刷新已保存结果；不能覆盖原文。" : E === "quote_unavailable" ? "报价提取服务目前不可用，请检查配置。" : E === "quote_failed" ? "报价提取失败。请先刷新已保存结果，再决定是否手动重试。" : `${T(_)} 请先刷新已保存结果，确认是否已经提交。`), a("error");
      } finally {
        S.current = !1;
      }
    }
  }
  return /* @__PURE__ */ s.createElement(N, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ s.createElement(X, { gap: "sm" }, /* @__PURE__ */ s.createElement(De, { order: 4 }, "供应商报价原文（只读提取）"), /* @__PURE__ */ s.createElement(w, { size: "sm", c: "dimmed" }, "关联已有 SupplierPart，粘贴匿名纯文本。模型抽取字段，程序对照已存数据并保留原文证据；结果供人工核对，不会创建采购单。"), n === "checking" && /* @__PURE__ */ s.createElement(oe, { size: "sm", "aria-label": "读取已保存报价" }), n === "submitting" && /* @__PURE__ */ s.createElement(oe, { size: "sm", "aria-label": "提取报价" }), n === "error" && /* @__PURE__ */ s.createElement(Me, { color: "yellow" }, i), n === "missing" && /* @__PURE__ */ s.createElement(X, { gap: "sm" }, /* @__PURE__ */ s.createElement(
    je,
    {
      label: "SupplierPart ID",
      inputMode: "numeric",
      value: h,
      onChange: (_) => D(_.currentTarget.value),
      error: h && x === null ? "请输入正整数 ID。" : void 0,
      placeholder: "例如 123"
    }
  ), /* @__PURE__ */ s.createElement(
    Re,
    {
      label: "匿名报价原文",
      value: k,
      minRows: 5,
      onChange: (_) => C(_.currentTarget.value),
      description: `仅纯文本，最多 ${ee} 字节；当前 ${A} 字节。`,
      error: k && !te(k) ? A > ee ? "原文超过 8 KiB。" : "请输入非空报价原文。" : void 0,
      placeholder: "粘贴已去除联系人、电话等个人信息的报价文字"
    }
  ), /* @__PURE__ */ s.createElement(le, { onClick: q, disabled: !I }, "提交报价原文并提取")), n === "available" && o && /* @__PURE__ */ s.createElement(We, { quote: o }), /* @__PURE__ */ s.createElement(
    le,
    {
      variant: "light",
      onClick: () => B((_) => _ + 1),
      disabled: n === "submitting"
    },
    "刷新已保存报价"
  )));
}
const R = window.MantineCore.Alert, ce = window.MantineCore.Badge, O = window.MantineCore.Button, L = window.MantineCore.Group, ue = window.MantineCore.Loader, Y = window.MantineCore.Paper, j = window.MantineCore.Stack, m = window.MantineCore.Text, He = window.MantineCore.TextInput, Oe = window.MantineCore.Title, r = window.React, Q = "/plugin/inventree_procurement/";
function Fe({ line: t }) {
  const e = [
    ["需求量", t.required],
    ["已消耗", t.consumed],
    ["已分配", t.allocated],
    ["未满足需求", t.outstanding]
  ];
  return /* @__PURE__ */ r.createElement(Y, { withBorder: !0, p: "sm" }, /* @__PURE__ */ r.createElement(j, { gap: "xs" }, /* @__PURE__ */ r.createElement(m, { fw: 600 }, "BuildLine ", t.build_line_id, " · Part ", t.part_id), /* @__PURE__ */ r.createElement(L, { gap: "md" }, e.map(([n, a]) => /* @__PURE__ */ r.createElement(m, { key: n, size: "sm" }, n, "：", F(a)))), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "来源：", t.source ? `${t.source.model} #${t.source.pk}；${t.source.fields.join(", ")}` : "待核实"), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "计算：", t.source?.formula ?? "待核实")));
}
function Ne({ part: t }) {
  const e = t.available_stock, n = t.preliminary_shortage;
  return /* @__PURE__ */ r.createElement(Y, { withBorder: !0, p: "sm" }, /* @__PURE__ */ r.createElement(j, { gap: "xs" }, /* @__PURE__ */ r.createElement(m, { fw: 600 }, "Part ", t.part_id, " · ", t.name, " (", t.ipn, ")"), /* @__PURE__ */ r.createElement(m, { size: "sm" }, "关联 BuildLine：", t.build_line_ids.join(", ") || "待核实"), /* @__PURE__ */ r.createElement(L, { gap: "md" }, /* @__PURE__ */ r.createElement(m, { size: "sm" }, "选中生产单未满足需求：", F(t.selected_build_outstanding), " ", t.units), /* @__PURE__ */ r.createElement(m, { size: "sm" }, "可用库存：", F(e.value), " ", t.units), /* @__PURE__ */ r.createElement(m, { size: "sm" }, "初步缺口：", F(n.value), " ", t.units)), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "库存来源：", e.source ? `${e.source.model}.${e.source.field}；生产单 ${e.source.build_context_id}；BuildLine ${e.source.build_line_ids.join(", ")}` : "待核实"), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "位置范围：", e.location_scope ?? "待核实"), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "分配口径：", e.allocation_assumption ?? "待核实"), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "缺口依据：", n.source ? `${n.source.formula}；BuildLine ${n.source.build_line_ids.join(", ")}` : "待核实"), e.warning && /* @__PURE__ */ r.createElement(R, { color: "yellow" }, e.warning), n.warning && /* @__PURE__ */ r.createElement(R, { color: "yellow" }, n.warning)));
}
function Ke({ preview: t }) {
  return /* @__PURE__ */ r.createElement(j, { gap: "sm" }, /* @__PURE__ */ r.createElement(m, { size: "sm" }, "生产单：", t.build.reference, "（ID ", t.build.build_id, "；来源 Build #", t.build.source_pk ?? "待核实", "）"), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "快照摘要：", t.snapshot_digest, " · 分析时间：", t.analyzed_at ?? "待核实"), t.warnings.map((e, n) => /* @__PURE__ */ r.createElement(R, { key: n, color: "yellow" }, e)), t.lines.length === 0 && /* @__PURE__ */ r.createElement(m, { size: "sm", c: "dimmed" }, "此任务暂无物料需求行。"), t.lines.map((e) => /* @__PURE__ */ r.createElement(Fe, { key: e.build_line_id, line: e })), t.parts.length > 0 && /* @__PURE__ */ r.createElement(m, { fw: 600 }, "按 Part 汇总的库存与初步缺口（库存仅计一次）"), t.parts.map((e) => /* @__PURE__ */ r.createElement(Ne, { key: e.part_id, part: e })));
}
function Xe({ context: t }) {
  const [e, n] = r.useState("checking"), [a, o] = r.useState("checking"), [p, i] = r.useState([]), [b, h] = r.useState(""), [D, k] = r.useState(!1), [C, v] = r.useState(null), [B, S] = r.useState(!1), [l, f] = r.useState(null), [x, A] = r.useState("idle"), [I, q] = r.useState(null), [_, E] = r.useState(null), [U, _e] = r.useState(0), [ge, Ee] = r.useState(0), J = r.useRef(!1);
  r.useEffect(() => {
    const c = new AbortController();
    return n("checking"), o("checking"), v(null), t.api.get(`${Q}health/`, { signal: c.signal }).then(async ({ data: y }) => {
      if (c.signal.aborted) return;
      if (!(y !== null && typeof y == "object" && "status" in y && y.status === "ok")) {
        n("unavailable"), o("unavailable");
        return;
      }
      n("available");
      try {
        const $ = await t.api.get(`${Q}tasks/`, { signal: c.signal });
        if (c.signal.aborted) return;
        const H = he($.data);
        H === null ? o("unavailable") : (i(H), o("available"), S(!1));
      } catch ($) {
        c.signal.aborted || (o("unavailable"), v(T($)));
      }
    }).catch((y) => {
      c.signal.aborted || (n("unavailable"), o("unavailable"), v(T(y)));
    }), () => c.abort();
  }, [t.api, U]), r.useEffect(() => {
    if (!l) {
      A("idle"), q(null);
      return;
    }
    const c = new AbortController();
    return A("checking"), q(null), E(null), t.api.get(
      `${Q}tasks/${encodeURIComponent(l)}/preview/`,
      { signal: c.signal }
    ).then(({ data: y }) => {
      if (c.signal.aborted) return;
      const P = xe(y);
      P === null || P.task_id !== l ? (A("unavailable"), E("预览响应格式无法识别，请核对插件版本。")) : (q(P), A("available"));
    }).catch((y) => {
      c.signal.aborted || (A("unavailable"), E(T(y)));
    }), () => c.abort();
  }, [t.api, l, ge]);
  const G = me(b);
  async function we() {
    if (!(J.current || G === null || e !== "available" || a !== "available" || B)) {
      J.current = !0, k(!0), v(null);
      try {
        const c = await t.api.post(`${Q}tasks/`, { build_ids: [G] }), y = re(c.data);
        if (y === null) {
          S(!0), v("任务可能已创建，但响应格式无法识别。请先刷新任务列表核对。");
          return;
        }
        const P = await t.api.get(`${Q}tasks/${encodeURIComponent(y.id)}/`), $ = re(P.data);
        if ($ === null || $.id !== y.id) {
          S(!0), v("任务已创建，但回查结果无法核对。请刷新任务列表后再继续。");
          return;
        }
        i((H) => [$, ...H.filter((be) => be.id !== $.id)]), f($.id), h("");
      } catch (c) {
        S(!0), v(`${T(c)} 请先刷新任务列表核对，勿重复提交。`);
      } finally {
        J.current = !1, k(!1);
      }
    }
  }
  return /* @__PURE__ */ r.createElement(Y, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ r.createElement(j, { gap: "md" }, /* @__PURE__ */ r.createElement(L, { justify: "space-between", align: "start" }, /* @__PURE__ */ r.createElement("div", null, /* @__PURE__ */ r.createElement(Oe, { order: 3 }, "采购分析任务"), /* @__PURE__ */ r.createElement(m, { size: "sm", c: "dimmed" }, "只读预览；不会创建采购单或发起审批。")), /* @__PURE__ */ r.createElement(ce, { color: e === "available" ? "green" : e === "checking" ? "gray" : "red" }, e === "available" ? "插件可用" : e === "checking" ? "检查中" : "插件不可用")), e === "checking" && /* @__PURE__ */ r.createElement(ue, { size: "sm", "aria-label": "检查插件状态" }), e === "unavailable" && /* @__PURE__ */ r.createElement(R, { color: "yellow" }, "无法确认插件服务状态。"), /* @__PURE__ */ r.createElement(L, { align: "end" }, /* @__PURE__ */ r.createElement(
    He,
    {
      label: "生产单 ID",
      inputMode: "numeric",
      value: b,
      onChange: (c) => h(c.currentTarget.value),
      error: b && G === null ? "请输入一个正整数 ID。" : void 0,
      placeholder: "例如 123"
    }
  ), /* @__PURE__ */ r.createElement(
    O,
    {
      onClick: we,
      loading: D,
      disabled: G === null || e !== "available" || a !== "available" || B
    },
    "创建分析任务"
  )), C && /* @__PURE__ */ r.createElement(R, { color: "yellow" }, C), /* @__PURE__ */ r.createElement(j, { gap: "xs" }, /* @__PURE__ */ r.createElement(m, { fw: 600 }, "任务状态"), a === "checking" && /* @__PURE__ */ r.createElement(m, { size: "sm", c: "dimmed" }, "正在加载任务…"), a === "unavailable" && /* @__PURE__ */ r.createElement(m, { size: "sm", c: "dimmed" }, "任务列表不可用。"), a === "available" && p.length === 0 && /* @__PURE__ */ r.createElement(m, { size: "sm", c: "dimmed" }, "当前账户暂无任务。"), a === "available" && p.map((c) => /* @__PURE__ */ r.createElement(Y, { key: c.id, withBorder: !0, p: "xs" }, /* @__PURE__ */ r.createElement(L, { justify: "space-between" }, /* @__PURE__ */ r.createElement(m, { size: "sm", fw: 600 }, c.id), /* @__PURE__ */ r.createElement(ce, { variant: "light" }, c.status)), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "生产单 ID：", c.build_ids.join(", ") || "待核实", " · 更新于 ", c.updated_at), /* @__PURE__ */ r.createElement(O, { size: "xs", variant: "subtle", onClick: () => f(c.id) }, "查看只读预览")))), /* @__PURE__ */ r.createElement(j, { gap: "xs" }, /* @__PURE__ */ r.createElement(L, { justify: "space-between" }, /* @__PURE__ */ r.createElement(m, { fw: 600 }, "物料需求与库存预览"), l && /* @__PURE__ */ r.createElement(O, { size: "xs", variant: "light", onClick: () => Ee((c) => c + 1) }, "刷新预览")), !l && /* @__PURE__ */ r.createElement(m, { size: "sm", c: "dimmed" }, "选择任务后读取预览。"), x === "checking" && /* @__PURE__ */ r.createElement(ue, { size: "sm", "aria-label": "加载预览" }), x === "unavailable" && /* @__PURE__ */ r.createElement(R, { color: "yellow" }, _), x === "available" && I && /* @__PURE__ */ r.createElement(Ke, { preview: I }), x === "available" && I && l && /* @__PURE__ */ r.createElement(
    Be,
    {
      key: l,
      context: t,
      taskId: l,
      snapshotDigest: I.snapshot_digest
    }
  ), x === "available" && I && l && /* @__PURE__ */ r.createElement(Ge, { key: `quote-${l}`, context: t, taskId: l })), /* @__PURE__ */ r.createElement(m, { size: "xs", c: "dimmed" }, "数据来源：插件任务、BuildLine、Part 与已关联 SupplierPart 的只读接口。报价原文需人工粘贴；采购执行尚未接入。"), /* @__PURE__ */ r.createElement(O, { variant: "light", size: "xs", onClick: () => _e((c) => c + 1) }, "刷新任务列表")));
}
function Ye(t) {
  return /* @__PURE__ */ r.createElement(Xe, { context: t });
}
export {
  Ye as RenderProcurementPanel
};
