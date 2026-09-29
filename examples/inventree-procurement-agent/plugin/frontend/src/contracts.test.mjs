import assert from 'node:assert/strict';
import test from 'node:test';
import { displayFact, isCurrentExplanation, MAX_QUOTE_BYTES, parseBuildId, parseCreatedTask, parseDecisionPreview, parseExplanation, parsePreview, parseQuote, parseSupplierPartId, quoteByteLength, requestError, responseCode, responseStatus, validQuoteText } from './contracts.ts';

test('accepts one positive safe build ID only', () => {
  assert.equal(parseBuildId('42'), 42);
  for (const value of ['', '0', '-1', '1,2', '1.2', ' 1', '2147483648', '9007199254740992']) {
    assert.equal(parseBuildId(value), null);
  }
});

test('never invents missing preview facts', () => {
  const preview = parsePreview({
    task_id: 'task-1', snapshot_digest: 'abc', analyzed_at: null,
    preview: {
      schema_version: 1,
      build: { build_id: 10, reference: 'BUILD-10', source: { model: 'build.Build', pk: 10 } },
      lines: [{ build_line_id: 8, build_id: 10, part_id: 4, required: '12' }],
      parts: [{ part_id: 4, name: 'Part', ipn: 'P4', units: 'pcs', build_line_ids: [8],
        selected_build_outstanding: '12',
        available_stock: { value: null, warning: 'Stock annotation missing' },
        preliminary_shortage: { value: null, warning: 'Cannot compute' } }],
      warnings: []
    }
  });
  assert.ok(preview);
  assert.equal(preview.lines[0].required, '12');
  assert.equal(displayFact(preview.lines[0].outstanding), '待核实');
  assert.equal(displayFact(preview.parts[0].available_stock.value), '待核实');
  assert.equal(preview.parts[0].available_stock.warning, 'Stock annotation missing');
  assert.equal(parsePreview({ preview: { lines: [null] } }), null);
});

test('created task must have owned-task response shape', () => {
  const task = { id: 'abc', status: 'created', build_ids: [10], updated_at: '2026-09-28T00:00:00Z' };
  assert.deepEqual(parseCreatedTask({ task }), task);
  assert.equal(parseCreatedTask({ task: { ...task, build_ids: [0] } }), null);
});

test('reports common authentication and missing-resource failures', () => {
  assert.match(requestError({ response: { status: 400 } }), /格式/);
  assert.match(requestError({ response: { status: 401 } }), /重新登录/);
  assert.match(requestError({ response: { status: 403 } }), /权限/);
  assert.match(requestError({ response: { status: 404 } }), /不存在/);
  assert.match(requestError({ response: { status: 409 } }), /尚未生成/);
  assert.equal(responseStatus({ response: { status: 409 } }), 409);
  assert.equal(responseCode({ response: { data: { code: 'explanation_unavailable' } } }), 'explanation_unavailable');
  assert.equal(responseStatus({}), null);
});

test('AI explanation requires metadata and structured tool evidence', () => {
  const payload = { explanation: {
    text: 'Only the observed demand is known.', model: 'returned-model',
    snapshot_digest: 'sha256', generated_at: '2026-09-28T00:00:00Z',
    tool_calls: [{ name: 'read_task_snapshot', status: 'success', tool_call_id: 'call-1',
      result_sha256: 'a'.repeat(64) }]
  } };
  assert.deepEqual(parseExplanation(payload), payload.explanation);
  assert.equal(isCurrentExplanation(payload.explanation, 'sha256'), true);
  assert.equal(isCurrentExplanation(payload.explanation, 'other'), false);
  assert.equal(parseExplanation({ explanation: { ...payload.explanation, tool_calls: [] } }), null);
  assert.equal(parseExplanation({ explanation: { ...payload.explanation, tool_calls: [{ name: 'read_task_snapshot', status: 'error' }] } }), null);
  assert.equal(parseExplanation({ explanation: { ...payload.explanation, tool_calls: [
    { ...payload.explanation.tool_calls[0], tool_call_id: '' }
  ] } }), null);
  assert.equal(parseExplanation({ explanation: { ...payload.explanation, tool_calls: [
    { ...payload.explanation.tool_calls[0], result_sha256: 'not-a-digest' }
  ] } }), null);
  assert.equal(parseExplanation({ explanation: { ...payload.explanation, snapshot_digest: '' } }), null);
});

test('quote input validates positive ID and UTF-8 byte length', () => {
  assert.equal(parseSupplierPartId('42'), 42);
  assert.equal(parseSupplierPartId('0'), null);
  assert.equal(parseSupplierPartId('42.0'), null);
  assert.equal(validQuoteText('  '), false);
  assert.equal(quoteByteLength('报价'), 6);
  assert.equal(validQuoteText('a'.repeat(MAX_QUOTE_BYTES)), true);
  assert.equal(validQuoteText('a'.repeat(MAX_QUOTE_BYTES + 1)), false);
});

test('saved quote requires exact source evidence and actual tool call', () => {
  const source = '😀 报价 USD 12.50';
  const start = Array.from(source).indexOf('U');
  const evidence = { value: 'USD', evidence: 'USD', start, end: start + 3 };
  const extracted = Object.fromEntries([
    'supplier_name', 'sku', 'unit_price', 'currency', 'price_unit',
    'pack_quantity', 'valid_until', 'lead_time'
  ].map((field) => [field, field === 'currency' ? evidence : null]));
  const quote = {
    supplier_part_id: 7, source_sha256: 'a'.repeat(64), source_text: source,
    created_at: '2026-09-28T00:00:00Z', model: 'deepseek-flash', extracted,
    checks: [{ field: 'currency', status: 'unverified', message: 'No stored price tier.' }],
    tool_calls: [{ name: 'read_quote_snapshot', status: 'success', tool_call_id: 'call-7',
      result_sha256: 'b'.repeat(64) }]
  };
  assert.deepEqual(parseQuote({ quote }), quote);
  assert.equal(parseQuote({ quote: { ...quote, extracted: { ...extracted,
    currency: { ...evidence, end: start + 4 } } } }), null);
  assert.equal(parseQuote({ quote: { ...quote, checks: [{ field: 'currency', status: 'approved', message: 'ok' }] } }), null);
  assert.equal(parseQuote({ quote: { ...quote, tool_calls: [] } }), null);
  assert.equal(parseQuote({ quote: { ...quote, tool_calls: [{ ...quote.tool_calls[0], name: 'write_purchase_order' }] } }), null);
  assert.equal(parseQuote({ quote: { ...quote, source_sha256: 'bad' } }), null);
});

test('decision preview never accepts a proposed order quantity or total', () => {
  const row = {
    part_id: 4, name: 'Part', units: 'pcs', preliminary_shortage: '12',
    supplier_part_id: 7, quote_unit_price: '2.50', quote_currency: 'USD',
    quote_price_unit: 'pcs', blockers: [{ code: 'incoming_supply', message: 'Check incoming supply.' }],
    order_quantity: null, estimated_total: null
  };
  const payload = {
    task_id: 'task-1', snapshot_digest: 'a'.repeat(64),
    quote_source_sha256: 'b'.repeat(64), status: 'needs_review', rows: [row]
  };
  assert.deepEqual(parseDecisionPreview(payload), payload);
  assert.deepEqual(parseDecisionPreview({ ...payload, quote_source_sha256: null, rows: [{
    ...row, supplier_part_id: null, quote_unit_price: null, quote_currency: null, quote_price_unit: null
  }] })?.quote_source_sha256, null);
  assert.equal(parseDecisionPreview({ ...payload, status: 'approved' }), null);
  assert.equal(parseDecisionPreview({ ...payload, rows: [{ ...row, order_quantity: '12' }] }), null);
  assert.equal(parseDecisionPreview({ ...payload, rows: [{ ...row, estimated_total: '30.00' }] }), null);
  assert.equal(parseDecisionPreview({ ...payload, rows: [{ ...row, estimated_total: undefined }] }), null);
  assert.equal(parseDecisionPreview({ ...payload, rows: [{ ...row, preliminary_shortage: 'bad' }] }), null);
  assert.equal(parseDecisionPreview({ ...payload, rows: [{ ...row, blockers: [{ code: '', message: 'Check' }] }] }), null);
  assert.equal(parseDecisionPreview({ ...payload, quote_source_sha256: '' }), null);
});
