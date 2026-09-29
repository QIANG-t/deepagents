const Y = {
  supplier_name: "供应商名称",
  sku: "供应商料号",
  unit_price: "单价",
  currency: "币种",
  price_unit: "计价单位",
  pack_quantity: "包装数量",
  valid_until: "报价有效期",
  lead_time: "交期"
}, ae = 8192;
function u(t) {
  return t !== null && typeof t == "object" && !Array.isArray(t) ? t : null;
}
function w(t) {
  return typeof t == "number" && Number.isSafeInteger(t) && t > 0 ? t : null;
}
function te(t) {
  return Array.isArray(t) ? t.filter((e) => w(e) !== null) : [];
}
function ge(t) {
  return Array.isArray(t) ? t.filter((e) => typeof e == "string") : [];
}
function B(t) {
  return typeof t == "string" && /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(t) ? t : null;
}
function we(t) {
  if (!/^[1-9][0-9]*$/.test(t)) return null;
  const e = w(Number(t));
  return e !== null && e <= 2147483647 ? e : null;
}
function xe(t) {
  return we(t);
}
function Ee(t) {
  return new TextEncoder().encode(t).length;
}
function se(t) {
  return t.trim().length > 0 && Ee(t) <= ae;
}
function ye(t) {
  const e = u(t);
  return !e || typeof e.id != "string" || typeof e.status != "string" || typeof e.updated_at != "string" || !Array.isArray(e.build_ids) || !e.build_ids.every((n) => w(n) !== null) ? null : e;
}
function ze(t) {
  const e = u(t);
  if (!e || !Array.isArray(e.tasks)) return null;
  const n = e.tasks.map(ye);
  return n.every((s) => s !== null) ? n : null;
}
function ie(t) {
  return ye(u(t)?.task);
}
function Se(t) {
  const e = u(t);
  if (!e || w(e.build_line_id) === null || w(e.build_id) === null || w(e.part_id) === null) return null;
  const n = u(e.source);
  return {
    build_line_id: w(e.build_line_id),
    build_id: w(e.build_id),
    part_id: w(e.part_id),
    required: B(e.required),
    consumed: B(e.consumed),
    allocated: B(e.allocated),
    outstanding: B(e.outstanding),
    source: n && typeof n.model == "string" && w(n.pk) !== null && typeof n.formula == "string" ? { model: n.model, pk: w(n.pk), fields: ge(n.fields), formula: n.formula } : null
  };
}
function $e(t) {
  const e = u(t);
  if (!e || w(e.part_id) === null) return null;
  const n = u(e.available_stock), s = u(e.preliminary_shortage), a = u(n?.source), c = u(s?.source), i = u(n?.location_assumption);
  return {
    part_id: w(e.part_id),
    name: typeof e.name == "string" ? e.name : "待核实",
    ipn: typeof e.ipn == "string" ? e.ipn : "待核实",
    units: typeof e.units == "string" ? e.units : "待核实",
    build_line_ids: te(e.build_line_ids),
    selected_build_outstanding: B(e.selected_build_outstanding),
    available_stock: {
      value: B(n?.value),
      source: a && typeof a.model == "string" && typeof a.field == "string" && w(a.build_context_id) !== null ? {
        model: a.model,
        field: a.field,
        build_context_id: w(a.build_context_id),
        build_line_ids: te(a.build_line_ids)
      } : null,
      location_scope: typeof i?.scope == "string" ? i.scope : null,
      allocation_assumption: typeof n?.allocation_assumption == "string" ? n.allocation_assumption : null,
      warning: typeof n?.warning == "string" ? n.warning : null
    },
    preliminary_shortage: {
      value: B(s?.value),
      source: c && typeof c.formula == "string" ? { formula: c.formula, build_line_ids: te(c.build_line_ids) } : null,
      warning: typeof s?.warning == "string" ? s.warning : null
    }
  };
}
function Ae(t) {
  const e = u(t), n = u(e?.preview), s = u(n?.build);
  if (!e || typeof e.task_id != "string" || typeof e.snapshot_digest != "string" || !n || n.schema_version !== 1 || !s || w(s.build_id) === null || !Array.isArray(n.lines) || !Array.isArray(n.parts)) return null;
  const a = n.lines.map(Se), c = n.parts.map($e);
  return a.some((i) => i === null) || c.some((i) => i === null) ? null : {
    task_id: e.task_id,
    snapshot_digest: e.snapshot_digest,
    analyzed_at: typeof e.analyzed_at == "string" ? e.analyzed_at : null,
    build: {
      build_id: w(s.build_id),
      reference: typeof s.reference == "string" ? s.reference : "待核实",
      source_pk: w(u(s.source)?.pk)
    },
    lines: a,
    parts: c,
    warnings: ge(n.warnings)
  };
}
function j(t) {
  return t === null ? "待核实" : t;
}
function Me(t) {
  const e = u(u(t)?.explanation);
  if (!e || typeof e.text != "string" || !e.text.trim() || typeof e.model != "string" || !e.model.trim() || typeof e.snapshot_digest != "string" || !e.snapshot_digest || typeof e.generated_at != "string" || !e.generated_at || !Array.isArray(e.tool_calls) || e.tool_calls.length !== 1) return null;
  const n = e.tool_calls.map(u);
  return n.some((s) => !s || s.name !== "read_task_snapshot" || s.status !== "success" || typeof s.tool_call_id != "string" || !s.tool_call_id.trim() || typeof s.result_sha256 != "string" || !/^[a-f0-9]{64}$/.test(s.result_sha256)) ? null : {
    text: e.text,
    model: e.model,
    snapshot_digest: e.snapshot_digest,
    generated_at: e.generated_at,
    tool_calls: n.map((s) => ({
      name: s.name,
      status: s.status,
      tool_call_id: s.tool_call_id,
      result_sha256: s.result_sha256
    }))
  };
}
function Pe(t, e) {
  return t.snapshot_digest === e;
}
function Te(t, e) {
  if (t === null) return null;
  const n = u(t);
  if (!(!n || typeof n.value != "string" || !n.value.trim() || typeof n.evidence != "string" || !n.evidence.trim() || typeof n.start != "number" || !Number.isSafeInteger(n.start) || n.start < 0 || typeof n.end != "number" || !Number.isSafeInteger(n.end) || n.end <= n.start || Array.from(e).slice(n.start, n.end).join("") !== n.evidence))
    return { value: n.value, evidence: n.evidence, start: n.start, end: n.end };
}
function Be(t) {
  const e = u(u(t)?.quote), n = u(e?.extracted);
  if (!e || w(e.supplier_part_id) === null || typeof e.source_sha256 != "string" || !/^[a-f0-9]{64}$/.test(e.source_sha256) || typeof e.source_text != "string" || !se(e.source_text) || typeof e.created_at != "string" || !e.created_at.trim() || typeof e.model != "string" || !e.model.trim() || !n || !Array.isArray(e.checks) || !Array.isArray(e.tool_calls) || e.tool_calls.length !== 1) return null;
  const s = {};
  for (const i of Object.keys(Y)) {
    const b = Te(n[i], e.source_text);
    if (b === void 0) return null;
    s[i] = b;
  }
  const a = e.checks.map(u);
  if (a.some((i) => !i || typeof i.field != "string" || !i.field.trim() || !["match", "conflict", "unverified"].includes(i.status) || typeof i.message != "string" || !i.message.trim())) return null;
  const c = e.tool_calls.map(u);
  return c.some((i) => !i || i.name !== "read_quote_snapshot" || i.status !== "success" || typeof i.tool_call_id != "string" || !i.tool_call_id.trim() || typeof i.result_sha256 != "string" || !/^[a-f0-9]{64}$/.test(i.result_sha256)) ? null : {
    supplier_part_id: e.supplier_part_id,
    source_sha256: e.source_sha256,
    source_text: e.source_text,
    created_at: e.created_at,
    model: e.model,
    extracted: s,
    checks: a.map((i) => ({
      field: i.field,
      status: i.status,
      message: i.message
    })),
    tool_calls: c.map((i) => ({
      name: "read_quote_snapshot",
      status: "success",
      tool_call_id: i.tool_call_id,
      result_sha256: i.result_sha256
    }))
  };
}
function Ie(t) {
  const e = u(t);
  if (!e || typeof e.task_id != "string" || !e.task_id.trim() || typeof e.snapshot_digest != "string" || !/^[a-f0-9]{64}$/.test(e.snapshot_digest) || e.quote_source_sha256 !== null && (typeof e.quote_source_sha256 != "string" || !/^[a-f0-9]{64}$/.test(e.quote_source_sha256)) || e.status !== "needs_review" || !Array.isArray(e.rows)) return null;
  const n = [];
  for (const s of e.rows) {
    const a = u(s);
    if (!a || w(a.part_id) === null || typeof a.name != "string" || !a.name.trim() || typeof a.units != "string" || typeof a.preliminary_shortage != "string" && a.preliminary_shortage !== null || a.preliminary_shortage !== null && B(a.preliminary_shortage) === null || a.supplier_part_id !== null && w(a.supplier_part_id) === null || a.quote_unit_price !== null && B(a.quote_unit_price) === null || a.quote_currency !== null && (typeof a.quote_currency != "string" || !a.quote_currency.trim()) || a.quote_price_unit !== null && (typeof a.quote_price_unit != "string" || !a.quote_price_unit.trim()) || !Array.isArray(a.blockers) || a.order_quantity !== null || a.estimated_total !== null) return null;
    const c = a.blockers.map(u);
    if (c.some((i) => !i || typeof i.code != "string" || !i.code.trim() || typeof i.message != "string" || !i.message.trim())) return null;
    n.push({
      part_id: a.part_id,
      name: a.name,
      units: a.units,
      preliminary_shortage: a.preliminary_shortage,
      supplier_part_id: a.supplier_part_id,
      quote_unit_price: a.quote_unit_price,
      quote_currency: a.quote_currency,
      quote_price_unit: a.quote_price_unit,
      blockers: c.map((i) => ({ code: i.code, message: i.message })),
      order_quantity: null,
      estimated_total: null
    });
  }
  return {
    task_id: e.task_id,
    snapshot_digest: e.snapshot_digest,
    quote_source_sha256: e.quote_source_sha256,
    status: "needs_review",
    rows: n
  };
}
function Z(t) {
  const e = u(u(t)?.response)?.status;
  return typeof e == "number" ? e : null;
}
function U(t) {
  const e = u(u(u(t)?.response)?.data)?.code;
  return typeof e == "string" ? e : null;
}
function I(t) {
  const e = Z(t);
  return e === 400 ? "请求格式有误，请检查生产单 ID。" : e === 401 ? "登录已失效，请重新登录后重试。" : e === 403 ? "没有读取生产单、物料或库存所需的权限。" : e === 404 ? "生产单或任务不存在，或当前用户无法访问。" : e === 409 ? "预览尚未生成，请稍后刷新。" : "请求失败，请检查连接后重试。";
}
const qe = window.MantineCore.Alert, le = window.MantineCore.Button, Re = window.MantineCore.Group, oe = window.MantineCore.Loader, ce = window.MantineCore.Paper, ne = window.MantineCore.Stack, M = window.MantineCore.Text, Le = window.MantineCore.Title, p = window.React;
function De({ context: t, taskId: e, snapshotDigest: n }) {
  const [s, a] = p.useState("checking"), [c, i] = p.useState(null), [b, y] = p.useState(null), [R, z] = p.useState(0), S = p.useRef(!1), d = `/plugin/inventree_procurement/tasks/${encodeURIComponent(e)}/explanation/`;
  function v(o) {
    const g = Me(o);
    return g === null ? (y("解释响应格式无法识别，请核对插件版本。"), a("error"), !1) : Pe(g, n) ? (i(g), a("available"), !0) : (y("解释引用的快照与当前预览不同，已停止展示。请刷新预览后核对。"), a("error"), !1);
  }
  p.useEffect(() => {
    const o = new AbortController();
    return a("checking"), i(null), y(null), t.api.get(d, { signal: o.signal }).then(({ data: g }) => {
      o.signal.aborted || v(g);
    }).catch((g) => {
      o.signal.aborted || (Z(g) === 409 && U(g) === "explanation_unavailable" ? a("missing") : (y(U(g) === "preview_unavailable" ? "事实预览尚不可用，请先刷新预览。" : I(g)), a("error")));
    }), () => o.abort();
  }, [t.api, d, n, R]);
  async function h() {
    if (!(S.current || s === "generating" || s === "checking" || s === "available")) {
      S.current = !0, a("generating"), i(null), y(null);
      try {
        const o = await t.api.post(d);
        v(o.data);
      } catch (o) {
        const g = U(o);
        y(g === "explanation_busy" ? "另一项解释生成正在进行，请稍后刷新已保存解释。" : g === "snapshot_changed" ? "生成期间事实快照已改变，请刷新预览。" : g === "explanation_unavailable" ? "AI 解释服务目前不可用，请检查服务配置。" : g === "explanation_failed" ? "AI 解释生成失败，请稍后手动重试。" : `${I(o)} 请先刷新已保存解释，确认是否已经生成。`), a("error");
      } finally {
        S.current = !1;
      }
    }
  }
  return /* @__PURE__ */ p.createElement(ce, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ p.createElement(ne, { gap: "sm" }, /* @__PURE__ */ p.createElement(Le, { order: 4 }, "AI 解释"), /* @__PURE__ */ p.createElement(M, { size: "sm", c: "dimmed" }, "这是对已保存事实快照的文字解释，不是采购建议；上方数量与库存仍以确定性预览为准。"), s === "checking" && /* @__PURE__ */ p.createElement(oe, { size: "sm", "aria-label": "读取已保存解释" }), s === "missing" && /* @__PURE__ */ p.createElement(M, { size: "sm", c: "dimmed" }, "此任务尚未生成 AI 解释。"), s === "generating" && /* @__PURE__ */ p.createElement(oe, { size: "sm", "aria-label": "生成 AI 解释" }), s === "error" && /* @__PURE__ */ p.createElement(qe, { color: "yellow" }, b), s === "available" && c && /* @__PURE__ */ p.createElement(ne, { gap: "xs" }, /* @__PURE__ */ p.createElement(M, { size: "sm" }, "模型：", c.model), /* @__PURE__ */ p.createElement(M, { size: "sm" }, "生成时间：", c.generated_at), /* @__PURE__ */ p.createElement(M, { size: "xs", c: "dimmed" }, "关联快照：", c.snapshot_digest), /* @__PURE__ */ p.createElement(M, { size: "sm", style: { whiteSpace: "pre-wrap" } }, c.text), /* @__PURE__ */ p.createElement(M, { fw: 600, size: "sm" }, "实际工具调用证据"), c.tool_calls.map((o, g) => /* @__PURE__ */ p.createElement(ce, { key: g, withBorder: !0, p: "xs" }, /* @__PURE__ */ p.createElement(ne, { gap: 2 }, /* @__PURE__ */ p.createElement(M, { size: "xs" }, o.name, " · ", o.status), /* @__PURE__ */ p.createElement(M, { size: "xs", style: { overflowWrap: "anywhere" } }, "调用 ID：", o.tool_call_id), /* @__PURE__ */ p.createElement(M, { size: "xs", style: { overflowWrap: "anywhere" } }, "结果 SHA-256：", o.result_sha256))))), /* @__PURE__ */ p.createElement(Re, null, /* @__PURE__ */ p.createElement(
    le,
    {
      onClick: h,
      loading: s === "generating",
      disabled: s === "checking" || s === "generating" || s === "available"
    },
    "生成 AI 解释"
  ), /* @__PURE__ */ p.createElement(
    le,
    {
      variant: "light",
      onClick: () => z((o) => o + 1),
      disabled: s === "generating"
    },
    "刷新已保存解释"
  ))));
}
const je = window.MantineCore.Alert, Ue = window.MantineCore.Badge, ue = window.MantineCore.Button, Ge = window.MantineCore.Group, de = window.MantineCore.Loader, X = window.MantineCore.Paper, J = window.MantineCore.Stack, C = window.MantineCore.Text, Qe = window.MantineCore.Textarea, We = window.MantineCore.TextInput, He = window.MantineCore.Title, l = window.React, Oe = Object.keys(Y), Fe = { match: "匹配", conflict: "冲突", unverified: "待核实" }, Ne = { match: "green", conflict: "red", unverified: "yellow" };
function Ke({ quote: t }) {
  return /* @__PURE__ */ l.createElement(J, { gap: "sm" }, /* @__PURE__ */ l.createElement(C, { size: "sm" }, "关联 SupplierPart ID：", t.supplier_part_id), /* @__PURE__ */ l.createElement(C, { size: "sm" }, "模型：", t.model, " · 提取时间：", t.created_at), /* @__PURE__ */ l.createElement(C, { size: "xs", c: "dimmed", style: { overflowWrap: "anywhere" } }, "原文 SHA-256：", t.source_sha256), /* @__PURE__ */ l.createElement("details", null, /* @__PURE__ */ l.createElement("summary", null, "查看已保存的报价原文"), /* @__PURE__ */ l.createElement(C, { size: "sm", style: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" } }, t.source_text)), /* @__PURE__ */ l.createElement(C, { fw: 600, size: "sm" }, "抽取字段与原文证据"), Oe.map((e) => {
    const n = t.extracted[e];
    return /* @__PURE__ */ l.createElement(X, { key: e, withBorder: !0, p: "xs" }, /* @__PURE__ */ l.createElement(C, { size: "sm", fw: 600 }, Y[e], "：", n?.value ?? "待核实"), n && /* @__PURE__ */ l.createElement(C, { size: "xs", style: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" } }, "原文片段：", n.evidence, "（字符位置 ", n.start, "–", n.end, "，结束位置不含）"));
  }), /* @__PURE__ */ l.createElement(C, { fw: 600, size: "sm" }, "对照检查"), t.checks.length === 0 && /* @__PURE__ */ l.createElement(C, { size: "sm", c: "dimmed" }, "暂无可核对的字段。"), t.checks.map((e, n) => /* @__PURE__ */ l.createElement(X, { key: n, withBorder: !0, p: "xs" }, /* @__PURE__ */ l.createElement(Ge, { gap: "xs" }, /* @__PURE__ */ l.createElement(Ue, { color: Ne[e.status] }, Fe[e.status]), /* @__PURE__ */ l.createElement(C, { size: "sm", fw: 600 }, e.field === "price_break" ? "价格阶梯对照" : Y[e.field] ?? e.field)), /* @__PURE__ */ l.createElement(C, { size: "sm" }, e.message))), /* @__PURE__ */ l.createElement(C, { fw: 600, size: "sm" }, "实际工具调用证据"), t.tool_calls.map((e) => /* @__PURE__ */ l.createElement(X, { key: e.tool_call_id, withBorder: !0, p: "xs" }, /* @__PURE__ */ l.createElement(J, { gap: 2 }, /* @__PURE__ */ l.createElement(C, { size: "xs" }, e.name, " · ", e.status), /* @__PURE__ */ l.createElement(C, { size: "xs", style: { overflowWrap: "anywhere" } }, "调用 ID：", e.tool_call_id), /* @__PURE__ */ l.createElement(C, { size: "xs", style: { overflowWrap: "anywhere" } }, "结果 SHA-256：", e.result_sha256)))));
}
function Xe({ context: t, taskId: e }) {
  const [n, s] = l.useState("checking"), [a, c] = l.useState(null), [i, b] = l.useState(null), [y, R] = l.useState(""), [z, S] = l.useState(""), [d, v] = l.useState(0), h = l.useRef(!1), o = `/plugin/inventree_procurement/tasks/${encodeURIComponent(e)}/quote/`;
  function g(E, k) {
    const H = Be(E);
    return !H || k && H.supplier_part_id !== k ? (b("报价结果格式或关联 SupplierPart 无法核对，请刷新已保存结果。"), s("error"), !1) : (c(H), s("available"), !0);
  }
  l.useEffect(() => {
    const E = new AbortController();
    return s("checking"), c(null), b(null), t.api.get(o, { signal: E.signal }).then(({ data: k }) => {
      E.signal.aborted || g(k);
    }).catch((k) => {
      E.signal.aborted || (Z(k) === 409 && U(k) === "quote_unavailable" ? s("missing") : (b(I(k)), s("error")));
    }), () => E.abort();
  }, [t.api, o, d]);
  const $ = xe(y), q = Ee(z), A = n === "missing" && $ !== null && se(z);
  async function W() {
    if (!(h.current || !A || $ === null)) {
      h.current = !0, s("submitting"), b(null);
      try {
        const E = await t.api.post(o, { supplier_part_id: $, text: z });
        g(E.data, $) && S("");
      } catch (E) {
        const k = U(E);
        b(k === "quote_immutable" ? "此任务已保存另一份报价原文。请刷新已保存结果；不能覆盖原文。" : k === "quote_unavailable" ? "报价提取服务目前不可用，请检查配置。" : k === "quote_failed" ? "报价提取失败。请先刷新已保存结果，再决定是否手动重试。" : `${I(E)} 请先刷新已保存结果，确认是否已经提交。`), s("error");
      } finally {
        h.current = !1;
      }
    }
  }
  return /* @__PURE__ */ l.createElement(X, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ l.createElement(J, { gap: "sm" }, /* @__PURE__ */ l.createElement(He, { order: 4 }, "供应商报价原文（只读提取）"), /* @__PURE__ */ l.createElement(C, { size: "sm", c: "dimmed" }, "关联已有 SupplierPart，粘贴匿名纯文本。模型抽取字段，程序对照已存数据并保留原文证据；结果供人工核对，不会创建采购单。"), n === "checking" && /* @__PURE__ */ l.createElement(de, { size: "sm", "aria-label": "读取已保存报价" }), n === "submitting" && /* @__PURE__ */ l.createElement(de, { size: "sm", "aria-label": "提取报价" }), n === "error" && /* @__PURE__ */ l.createElement(je, { color: "yellow" }, i), n === "missing" && /* @__PURE__ */ l.createElement(J, { gap: "sm" }, /* @__PURE__ */ l.createElement(
    We,
    {
      label: "SupplierPart ID",
      inputMode: "numeric",
      value: y,
      onChange: (E) => R(E.currentTarget.value),
      error: y && $ === null ? "请输入正整数 ID。" : void 0,
      placeholder: "例如 123"
    }
  ), /* @__PURE__ */ l.createElement(
    Qe,
    {
      label: "匿名报价原文",
      value: z,
      minRows: 5,
      onChange: (E) => S(E.currentTarget.value),
      description: `仅纯文本，最多 ${ae} 字节；当前 ${q} 字节。`,
      error: z && !se(z) ? q > ae ? "原文超过 8 KiB。" : "请输入非空报价原文。" : void 0,
      placeholder: "粘贴已去除联系人、电话等个人信息的报价文字"
    }
  ), /* @__PURE__ */ l.createElement(ue, { onClick: W, disabled: !A }, "提交报价原文并提取")), n === "available" && a && /* @__PURE__ */ l.createElement(Ke, { quote: a }), /* @__PURE__ */ l.createElement(
    ue,
    {
      variant: "light",
      onClick: () => v((E) => E + 1),
      disabled: n === "submitting"
    },
    "刷新已保存报价"
  )));
}
const me = window.MantineCore.Alert, Ye = window.MantineCore.Button, Je = window.MantineCore.Group, Ve = window.MantineCore.Loader, pe = window.MantineCore.Paper, re = window.MantineCore.Stack, T = window.MantineCore.Text, Ze = window.MantineCore.Title, f = window.React;
function et({ context: t, taskId: e, snapshotDigest: n }) {
  const [s, a] = f.useState("checking"), [c, i] = f.useState(null), [b, y] = f.useState(null), [R, z] = f.useState(0), S = `/plugin/inventree_procurement/tasks/${encodeURIComponent(e)}/decision-preview/`;
  return f.useEffect(() => {
    const d = new AbortController();
    return a("checking"), i(null), y(null), t.api.get(S, { signal: d.signal }).then(({ data: v }) => {
      if (d.signal.aborted) return;
      const h = Ie(v);
      if (!h || h.task_id !== e || h.snapshot_digest !== n) {
        y("决策预览格式或生产单快照无法核对，请刷新任务预览。"), a("error");
        return;
      }
      i(h), a("available");
    }).catch((v) => {
      d.signal.aborted || (Z(v) === 409 && U(v) === "decision_preview_unavailable" ? a("unavailable") : (y(I(v)), a("error")));
    }), () => d.abort();
  }, [t.api, S, e, n, R]), /* @__PURE__ */ f.createElement(pe, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ f.createElement(re, { gap: "sm" }, /* @__PURE__ */ f.createElement(Ze, { order: 4 }, "采购决策预览（只读）"), /* @__PURE__ */ f.createElement(T, { size: "sm", c: "dimmed" }, "这里只整理缺口、报价和需要人工核实的问题。当前没有可下单数量或估算总价，也不会创建采购单。"), s === "checking" && /* @__PURE__ */ f.createElement(Ve, { size: "sm", "aria-label": "加载采购决策预览" }), s === "unavailable" && /* @__PURE__ */ f.createElement(T, { size: "sm", c: "dimmed" }, "生产单预览尚未生成，请刷新任务后再查看。"), s === "error" && /* @__PURE__ */ f.createElement(me, { color: "yellow" }, b), s === "available" && c && /* @__PURE__ */ f.createElement(re, { gap: "sm" }, /* @__PURE__ */ f.createElement(T, { size: "xs", c: "dimmed", style: { overflowWrap: "anywhere" } }, "生产单快照：", c.snapshot_digest, " · 报价原文：", c.quote_source_sha256 ?? "未关联"), c.rows.length === 0 && /* @__PURE__ */ f.createElement(T, { size: "sm", c: "dimmed" }, "暂无物料行。"), c.rows.map((d) => /* @__PURE__ */ f.createElement(pe, { key: d.part_id, withBorder: !0, p: "sm" }, /* @__PURE__ */ f.createElement(re, { gap: "xs" }, /* @__PURE__ */ f.createElement(T, { fw: 600 }, "Part ", d.part_id, " · ", d.name), /* @__PURE__ */ f.createElement(Je, { gap: "md" }, /* @__PURE__ */ f.createElement(T, { size: "sm" }, "初步缺口：", j(d.preliminary_shortage), " ", d.units), /* @__PURE__ */ f.createElement(T, { size: "sm" }, "SupplierPart：", d.supplier_part_id ?? "未关联")), /* @__PURE__ */ f.createElement(T, { size: "sm" }, "报价单价：", j(d.quote_unit_price), " ", d.quote_currency ?? "", " / ", d.quote_price_unit ?? "待核实"), /* @__PURE__ */ f.createElement(T, { size: "sm" }, "可下单数量：待核实 · 估算总价：待核实"), d.blockers.map((v, h) => /* @__PURE__ */ f.createElement(me, { key: `${v.code}-${h}`, color: "yellow", title: "需人工核实" }, v.message)))))), /* @__PURE__ */ f.createElement(Ye, { variant: "light", onClick: () => z((d) => d + 1) }, "刷新决策预览")));
}
const G = window.MantineCore.Alert, _e = window.MantineCore.Badge, K = window.MantineCore.Button, D = window.MantineCore.Group, fe = window.MantineCore.Loader, V = window.MantineCore.Paper, Q = window.MantineCore.Stack, _ = window.MantineCore.Text, tt = window.MantineCore.TextInput, nt = window.MantineCore.Title, r = window.React, O = "/plugin/inventree_procurement/";
function rt({ line: t }) {
  const e = [
    ["需求量", t.required],
    ["已消耗", t.consumed],
    ["已分配", t.allocated],
    ["未满足需求", t.outstanding]
  ];
  return /* @__PURE__ */ r.createElement(V, { withBorder: !0, p: "sm" }, /* @__PURE__ */ r.createElement(Q, { gap: "xs" }, /* @__PURE__ */ r.createElement(_, { fw: 600 }, "BuildLine ", t.build_line_id, " · Part ", t.part_id), /* @__PURE__ */ r.createElement(D, { gap: "md" }, e.map(([n, s]) => /* @__PURE__ */ r.createElement(_, { key: n, size: "sm" }, n, "：", j(s)))), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "来源：", t.source ? `${t.source.model} #${t.source.pk}；${t.source.fields.join(", ")}` : "待核实"), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "计算：", t.source?.formula ?? "待核实")));
}
function at({ part: t }) {
  const e = t.available_stock, n = t.preliminary_shortage;
  return /* @__PURE__ */ r.createElement(V, { withBorder: !0, p: "sm" }, /* @__PURE__ */ r.createElement(Q, { gap: "xs" }, /* @__PURE__ */ r.createElement(_, { fw: 600 }, "Part ", t.part_id, " · ", t.name, " (", t.ipn, ")"), /* @__PURE__ */ r.createElement(_, { size: "sm" }, "关联 BuildLine：", t.build_line_ids.join(", ") || "待核实"), /* @__PURE__ */ r.createElement(D, { gap: "md" }, /* @__PURE__ */ r.createElement(_, { size: "sm" }, "选中生产单未满足需求：", j(t.selected_build_outstanding), " ", t.units), /* @__PURE__ */ r.createElement(_, { size: "sm" }, "可用库存：", j(e.value), " ", t.units), /* @__PURE__ */ r.createElement(_, { size: "sm" }, "初步缺口：", j(n.value), " ", t.units)), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "库存来源：", e.source ? `${e.source.model}.${e.source.field}；生产单 ${e.source.build_context_id}；BuildLine ${e.source.build_line_ids.join(", ")}` : "待核实"), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "位置范围：", e.location_scope ?? "待核实"), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "分配口径：", e.allocation_assumption ?? "待核实"), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "缺口依据：", n.source ? `${n.source.formula}；BuildLine ${n.source.build_line_ids.join(", ")}` : "待核实"), e.warning && /* @__PURE__ */ r.createElement(G, { color: "yellow" }, e.warning), n.warning && /* @__PURE__ */ r.createElement(G, { color: "yellow" }, n.warning)));
}
function st({ preview: t }) {
  return /* @__PURE__ */ r.createElement(Q, { gap: "sm" }, /* @__PURE__ */ r.createElement(_, { size: "sm" }, "生产单：", t.build.reference, "（ID ", t.build.build_id, "；来源 Build #", t.build.source_pk ?? "待核实", "）"), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "快照摘要：", t.snapshot_digest, " · 分析时间：", t.analyzed_at ?? "待核实"), t.warnings.map((e, n) => /* @__PURE__ */ r.createElement(G, { key: n, color: "yellow" }, e)), t.lines.length === 0 && /* @__PURE__ */ r.createElement(_, { size: "sm", c: "dimmed" }, "此任务暂无物料需求行。"), t.lines.map((e) => /* @__PURE__ */ r.createElement(rt, { key: e.build_line_id, line: e })), t.parts.length > 0 && /* @__PURE__ */ r.createElement(_, { fw: 600 }, "按 Part 汇总的库存与初步缺口（库存仅计一次）"), t.parts.map((e) => /* @__PURE__ */ r.createElement(at, { key: e.part_id, part: e })));
}
function it({ context: t }) {
  const [e, n] = r.useState("checking"), [s, a] = r.useState("checking"), [c, i] = r.useState([]), [b, y] = r.useState(""), [R, z] = r.useState(!1), [S, d] = r.useState(null), [v, h] = r.useState(!1), [o, g] = r.useState(null), [$, q] = r.useState("idle"), [A, W] = r.useState(null), [E, k] = r.useState(null), [H, he] = r.useState(0), [be, ve] = r.useState(0), ee = r.useRef(!1);
  r.useEffect(() => {
    const m = new AbortController();
    return n("checking"), a("checking"), d(null), t.api.get(`${O}health/`, { signal: m.signal }).then(async ({ data: x }) => {
      if (m.signal.aborted) return;
      if (!(x !== null && typeof x == "object" && "status" in x && x.status === "ok")) {
        n("unavailable"), a("unavailable");
        return;
      }
      n("available");
      try {
        const P = await t.api.get(`${O}tasks/`, { signal: m.signal });
        if (m.signal.aborted) return;
        const N = ze(P.data);
        N === null ? a("unavailable") : (i(N), a("available"), h(!1));
      } catch (P) {
        m.signal.aborted || (a("unavailable"), d(I(P)));
      }
    }).catch((x) => {
      m.signal.aborted || (n("unavailable"), a("unavailable"), d(I(x)));
    }), () => m.abort();
  }, [t.api, H]), r.useEffect(() => {
    if (!o) {
      q("idle"), W(null);
      return;
    }
    const m = new AbortController();
    return q("checking"), W(null), k(null), t.api.get(
      `${O}tasks/${encodeURIComponent(o)}/preview/`,
      { signal: m.signal }
    ).then(({ data: x }) => {
      if (m.signal.aborted) return;
      const L = Ae(x);
      L === null || L.task_id !== o ? (q("unavailable"), k("预览响应格式无法识别，请核对插件版本。")) : (W(L), q("available"));
    }).catch((x) => {
      m.signal.aborted || (q("unavailable"), k(I(x)));
    }), () => m.abort();
  }, [t.api, o, be]);
  const F = we(b);
  async function ke() {
    if (!(ee.current || F === null || e !== "available" || s !== "available" || v)) {
      ee.current = !0, z(!0), d(null);
      try {
        const m = await t.api.post(`${O}tasks/`, { build_ids: [F] }), x = ie(m.data);
        if (x === null) {
          h(!0), d("任务可能已创建，但响应格式无法识别。请先刷新任务列表核对。");
          return;
        }
        const L = await t.api.get(`${O}tasks/${encodeURIComponent(x.id)}/`), P = ie(L.data);
        if (P === null || P.id !== x.id) {
          h(!0), d("任务已创建，但回查结果无法核对。请刷新任务列表后再继续。");
          return;
        }
        i((N) => [P, ...N.filter((Ce) => Ce.id !== P.id)]), g(P.id), y("");
      } catch (m) {
        h(!0), d(`${I(m)} 请先刷新任务列表核对，勿重复提交。`);
      } finally {
        ee.current = !1, z(!1);
      }
    }
  }
  return /* @__PURE__ */ r.createElement(V, { withBorder: !0, p: "md", radius: "md" }, /* @__PURE__ */ r.createElement(Q, { gap: "md" }, /* @__PURE__ */ r.createElement(D, { justify: "space-between", align: "start" }, /* @__PURE__ */ r.createElement("div", null, /* @__PURE__ */ r.createElement(nt, { order: 3 }, "采购分析任务"), /* @__PURE__ */ r.createElement(_, { size: "sm", c: "dimmed" }, "只读预览；不会创建采购单或发起审批。")), /* @__PURE__ */ r.createElement(_e, { color: e === "available" ? "green" : e === "checking" ? "gray" : "red" }, e === "available" ? "插件可用" : e === "checking" ? "检查中" : "插件不可用")), e === "checking" && /* @__PURE__ */ r.createElement(fe, { size: "sm", "aria-label": "检查插件状态" }), e === "unavailable" && /* @__PURE__ */ r.createElement(G, { color: "yellow" }, "无法确认插件服务状态。"), /* @__PURE__ */ r.createElement(D, { align: "end" }, /* @__PURE__ */ r.createElement(
    tt,
    {
      label: "生产单 ID",
      inputMode: "numeric",
      value: b,
      onChange: (m) => y(m.currentTarget.value),
      error: b && F === null ? "请输入一个正整数 ID。" : void 0,
      placeholder: "例如 123"
    }
  ), /* @__PURE__ */ r.createElement(
    K,
    {
      onClick: ke,
      loading: R,
      disabled: F === null || e !== "available" || s !== "available" || v
    },
    "创建分析任务"
  )), S && /* @__PURE__ */ r.createElement(G, { color: "yellow" }, S), /* @__PURE__ */ r.createElement(Q, { gap: "xs" }, /* @__PURE__ */ r.createElement(_, { fw: 600 }, "任务状态"), s === "checking" && /* @__PURE__ */ r.createElement(_, { size: "sm", c: "dimmed" }, "正在加载任务…"), s === "unavailable" && /* @__PURE__ */ r.createElement(_, { size: "sm", c: "dimmed" }, "任务列表不可用。"), s === "available" && c.length === 0 && /* @__PURE__ */ r.createElement(_, { size: "sm", c: "dimmed" }, "当前账户暂无任务。"), s === "available" && c.map((m) => /* @__PURE__ */ r.createElement(V, { key: m.id, withBorder: !0, p: "xs" }, /* @__PURE__ */ r.createElement(D, { justify: "space-between" }, /* @__PURE__ */ r.createElement(_, { size: "sm", fw: 600 }, m.id), /* @__PURE__ */ r.createElement(_e, { variant: "light" }, m.status)), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "生产单 ID：", m.build_ids.join(", ") || "待核实", " · 更新于 ", m.updated_at), /* @__PURE__ */ r.createElement(K, { size: "xs", variant: "subtle", onClick: () => g(m.id) }, "查看只读预览")))), /* @__PURE__ */ r.createElement(Q, { gap: "xs" }, /* @__PURE__ */ r.createElement(D, { justify: "space-between" }, /* @__PURE__ */ r.createElement(_, { fw: 600 }, "物料需求与库存预览"), o && /* @__PURE__ */ r.createElement(K, { size: "xs", variant: "light", onClick: () => ve((m) => m + 1) }, "刷新预览")), !o && /* @__PURE__ */ r.createElement(_, { size: "sm", c: "dimmed" }, "选择任务后读取预览。"), $ === "checking" && /* @__PURE__ */ r.createElement(fe, { size: "sm", "aria-label": "加载预览" }), $ === "unavailable" && /* @__PURE__ */ r.createElement(G, { color: "yellow" }, E), $ === "available" && A && /* @__PURE__ */ r.createElement(st, { preview: A }), $ === "available" && A && o && /* @__PURE__ */ r.createElement(
    De,
    {
      key: o,
      context: t,
      taskId: o,
      snapshotDigest: A.snapshot_digest
    }
  ), $ === "available" && A && o && /* @__PURE__ */ r.createElement(Xe, { key: `quote-${o}`, context: t, taskId: o }), $ === "available" && A && o && /* @__PURE__ */ r.createElement(
    et,
    {
      key: `decision-${o}`,
      context: t,
      taskId: o,
      snapshotDigest: A.snapshot_digest
    }
  )), /* @__PURE__ */ r.createElement(_, { size: "xs", c: "dimmed" }, "数据来源：插件任务、BuildLine、Part 与已关联 SupplierPart 的只读接口。报价原文需人工粘贴；采购执行尚未接入。"), /* @__PURE__ */ r.createElement(K, { variant: "light", size: "xs", onClick: () => he((m) => m + 1) }, "刷新任务列表")));
}
function lt(t) {
  return /* @__PURE__ */ r.createElement(it, { context: t });
}
export {
  lt as RenderProcurementPanel
};
