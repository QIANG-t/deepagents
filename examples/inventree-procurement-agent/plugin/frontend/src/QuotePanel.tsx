import type { InvenTreePluginContext } from '@inventreedb/ui';
import { Alert, Badge, Button, Group, Loader, Paper, Stack, Text, Textarea, TextInput, Title } from '@mantine/core';
import * as React from 'react';
import {
  MAX_QUOTE_BYTES, QUOTE_FIELD_LABELS, parseQuote, parseSupplierPartId,
  quoteByteLength, requestError, responseCode, responseStatus, validQuoteText
} from './contracts';
import type { Quote, QuoteFieldName } from './contracts';

type QuoteState = 'checking' | 'missing' | 'available' | 'error' | 'submitting';
const FIELD_NAMES = Object.keys(QUOTE_FIELD_LABELS) as QuoteFieldName[];
const CHECK_LABELS = { match: '匹配', conflict: '冲突', unverified: '待核实' } as const;
const CHECK_COLORS = { match: 'green', conflict: 'red', unverified: 'yellow' } as const;

function QuoteResult({ quote }: { quote: Quote }) {
  return (
    <Stack gap="sm">
      <Text size="sm">关联 SupplierPart ID：{quote.supplier_part_id}</Text>
      <Text size="sm">模型：{quote.model} · 提取时间：{quote.created_at}</Text>
      <Text size="xs" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
        原文 SHA-256：{quote.source_sha256}
      </Text>
      <details>
        <summary>查看已保存的报价原文</summary>
        <Text size="sm" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{quote.source_text}</Text>
      </details>
      <Text fw={600} size="sm">抽取字段与原文证据</Text>
      {FIELD_NAMES.map((name) => {
        const field = quote.extracted[name];
        return (
          <Paper key={name} withBorder p="xs">
            <Text size="sm" fw={600}>{QUOTE_FIELD_LABELS[name]}：{field?.value ?? '待核实'}</Text>
            {field && <Text size="xs" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
              原文片段：{field.evidence}（字符位置 {field.start}–{field.end}，结束位置不含）
            </Text>}
          </Paper>
        );
      })}
      <Text fw={600} size="sm">对照检查</Text>
      {quote.checks.length === 0 && <Text size="sm" c="dimmed">暂无可核对的字段。</Text>}
      {quote.checks.map((check, index) => (
        <Paper key={index} withBorder p="xs">
          <Group gap="xs"><Badge color={CHECK_COLORS[check.status]}>{CHECK_LABELS[check.status]}</Badge>
            <Text size="sm" fw={600}>{check.field === 'price_break' ? '价格阶梯对照' :
              QUOTE_FIELD_LABELS[check.field as QuoteFieldName] ?? check.field}</Text>
          </Group>
          <Text size="sm">{check.message}</Text>
        </Paper>
      ))}
      <Text fw={600} size="sm">实际工具调用证据</Text>
      {quote.tool_calls.map((call) => (
        <Paper key={call.tool_call_id} withBorder p="xs">
          <Stack gap={2}>
            <Text size="xs">{call.name} · {call.status}</Text>
            <Text size="xs" style={{ overflowWrap: 'anywhere' }}>调用 ID：{call.tool_call_id}</Text>
            <Text size="xs" style={{ overflowWrap: 'anywhere' }}>结果 SHA-256：{call.result_sha256}</Text>
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
}

export function QuotePanel({ context, taskId }: { context: InvenTreePluginContext; taskId: string }) {
  const [state, setState] = React.useState<QuoteState>('checking');
  const [quote, setQuote] = React.useState<Quote | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [supplierPartInput, setSupplierPartInput] = React.useState('');
  const [sourceText, setSourceText] = React.useState('');
  const [refresh, setRefresh] = React.useState(0);
  const submitLock = React.useRef(false);
  const url = `/plugin/inventree_procurement/tasks/${encodeURIComponent(taskId)}/quote/`;

  function accept(data: unknown, expectedSupplierPartId?: number): boolean {
    const parsed = parseQuote(data);
    if (!parsed || (expectedSupplierPartId && parsed.supplier_part_id !== expectedSupplierPartId)) {
      setError('报价结果格式或关联 SupplierPart 无法核对，请刷新已保存结果。');
      setState('error');
      return false;
    }
    setQuote(parsed);
    setState('available');
    return true;
  }

  React.useEffect(() => {
    const controller = new AbortController();
    setState('checking');
    setQuote(null);
    setError(null);
    context.api.get<unknown>(url, { signal: controller.signal })
      .then(({ data }) => { if (!controller.signal.aborted) accept(data); })
      .catch((failure) => {
        if (controller.signal.aborted) return;
        if (responseStatus(failure) === 409 && responseCode(failure) === 'quote_unavailable') {
          setState('missing');
        } else {
          setError(requestError(failure));
          setState('error');
        }
      });
    return () => controller.abort();
  }, [context.api, url, refresh]);

  const supplierPartId = parseSupplierPartId(supplierPartInput);
  const textBytes = quoteByteLength(sourceText);
  const canSubmit = state === 'missing' && supplierPartId !== null && validQuoteText(sourceText);

  async function submit() {
    if (submitLock.current || !canSubmit || supplierPartId === null) return;
    submitLock.current = true;
    setState('submitting');
    setError(null);
    try {
      const response = await context.api.post<unknown>(url, { supplier_part_id: supplierPartId, text: sourceText });
      if (accept(response.data, supplierPartId)) setSourceText('');
    } catch (failure) {
      const code = responseCode(failure);
      setError(code === 'quote_immutable'
        ? '此任务已保存另一份报价原文。请刷新已保存结果；不能覆盖原文。'
        : code === 'quote_unavailable'
          ? '报价提取服务目前不可用，请检查配置。'
          : code === 'quote_failed'
            ? '报价提取失败。请先刷新已保存结果，再决定是否手动重试。'
            : `${requestError(failure)} 请先刷新已保存结果，确认是否已经提交。`);
      setState('error');
    } finally {
      submitLock.current = false;
    }
  }

  return (
    <Paper withBorder p="md" radius="md">
      <Stack gap="sm">
        <Title order={4}>供应商报价原文（只读提取）</Title>
        <Text size="sm" c="dimmed">
          关联已有 SupplierPart，粘贴匿名纯文本。模型抽取字段，程序对照已存数据并保留原文证据；结果供人工核对，不会创建采购单。
        </Text>
        {state === 'checking' && <Loader size="sm" aria-label="读取已保存报价" />}
        {state === 'submitting' && <Loader size="sm" aria-label="提取报价" />}
        {state === 'error' && <Alert color="yellow">{error}</Alert>}
        {state === 'missing' && <Stack gap="sm">
          <TextInput label="SupplierPart ID" inputMode="numeric" value={supplierPartInput}
            onChange={(event) => setSupplierPartInput(event.currentTarget.value)}
            error={supplierPartInput && supplierPartId === null ? '请输入正整数 ID。' : undefined}
            placeholder="例如 123" />
          <Textarea label="匿名报价原文" value={sourceText} minRows={5}
            onChange={(event) => setSourceText(event.currentTarget.value)}
            description={`仅纯文本，最多 ${MAX_QUOTE_BYTES} 字节；当前 ${textBytes} 字节。`}
            error={sourceText && !validQuoteText(sourceText)
              ? textBytes > MAX_QUOTE_BYTES ? '原文超过 8 KiB。' : '请输入非空报价原文。' : undefined}
            placeholder="粘贴已去除联系人、电话等个人信息的报价文字" />
          <Button onClick={submit} disabled={!canSubmit}>提交报价原文并提取</Button>
        </Stack>}
        {state === 'available' && quote && <QuoteResult quote={quote} />}
        <Button variant="light" onClick={() => setRefresh((value) => value + 1)}
          disabled={state === 'submitting'}>刷新已保存报价</Button>
      </Stack>
    </Paper>
  );
}
