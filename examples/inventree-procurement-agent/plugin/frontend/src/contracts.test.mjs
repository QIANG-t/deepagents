import assert from 'node:assert/strict';
import test from 'node:test';
import { displayFact, isCurrentExplanation, parseBuildId, parseCreatedTask, parseExplanation, parsePreview, requestError, responseCode, responseStatus } from './contracts.ts';

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
