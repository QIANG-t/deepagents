import type { InvenTreePluginContext } from '@inventreedb/ui';
import { Alert, Button, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core';
import * as React from 'react';
import { isCurrentExplanation, parseExplanation, requestError, responseCode, responseStatus } from './contracts';
import type { Explanation } from './contracts';

type ExplanationState = 'checking' | 'missing' | 'available' | 'error' | 'generating';

export function ExplanationPanel({ context, taskId, snapshotDigest }: {
  context: InvenTreePluginContext;
  taskId: string;
  snapshotDigest: string;
}) {
  const [state, setState] = React.useState<ExplanationState>('checking');
  const [explanation, setExplanation] = React.useState<Explanation | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [refresh, setRefresh] = React.useState(0);
  const generationLock = React.useRef(false);
  const url = `/plugin/inventree_procurement/tasks/${encodeURIComponent(taskId)}/explanation/`;

  function accept(data: unknown): boolean {
    const parsed = parseExplanation(data);
    if (parsed === null) {
      setError('解释响应格式无法识别，请核对插件版本。');
      setState('error');
      return false;
    }
    if (!isCurrentExplanation(parsed, snapshotDigest)) {
      setError('解释引用的快照与当前预览不同，已停止展示。请刷新预览后核对。');
      setState('error');
      return false;
    }
    setExplanation(parsed);
    setState('available');
    return true;
  }

  React.useEffect(() => {
    const controller = new AbortController();
    setState('checking');
    setExplanation(null);
    setError(null);
    context.api.get<unknown>(url, { signal: controller.signal })
      .then(({ data }) => {
        if (!controller.signal.aborted) accept(data);
      })
      .catch((failure) => {
        if (controller.signal.aborted) return;
        if (responseStatus(failure) === 409 && responseCode(failure) === 'explanation_unavailable') {
          setState('missing');
        } else {
          setError(responseCode(failure) === 'preview_unavailable'
            ? '事实预览尚不可用，请先刷新预览。' : requestError(failure));
          setState('error');
        }
      });
    return () => controller.abort();
  }, [context.api, url, snapshotDigest, refresh]);

  async function generate() {
    if (generationLock.current || state === 'generating' || state === 'checking' || state === 'available') return;
    generationLock.current = true;
    setState('generating');
    setExplanation(null);
    setError(null);
    try {
      const response = await context.api.post<unknown>(url);
      accept(response.data);
    } catch (failure) {
      const code = responseCode(failure);
      setError(code === 'explanation_busy'
        ? '另一项解释生成正在进行，请稍后刷新已保存解释。'
        : code === 'snapshot_changed'
          ? '生成期间事实快照已改变，请刷新预览。'
          : code === 'explanation_unavailable'
            ? 'AI 解释服务目前不可用，请检查服务配置。'
            : code === 'explanation_failed'
              ? 'AI 解释生成失败，请稍后手动重试。'
              : `${requestError(failure)} 请先刷新已保存解释，确认是否已经生成。`);
      setState('error');
    } finally {
      generationLock.current = false;
    }
  }

  return (
    <Paper withBorder p="md" radius="md">
      <Stack gap="sm">
        <Title order={4}>AI 解释</Title>
        <Text size="sm" c="dimmed">
          这是对已保存事实快照的文字解释，不是采购建议；上方数量与库存仍以确定性预览为准。
        </Text>
        {state === 'checking' && <Loader size="sm" aria-label="读取已保存解释" />}
        {state === 'missing' && <Text size="sm" c="dimmed">此任务尚未生成 AI 解释。</Text>}
        {state === 'generating' && <Loader size="sm" aria-label="生成 AI 解释" />}
        {state === 'error' && <Alert color="yellow">{error}</Alert>}
        {state === 'available' && explanation && (
          <Stack gap="xs">
            <Text size="sm">模型：{explanation.model}</Text>
            <Text size="sm">生成时间：{explanation.generated_at}</Text>
            <Text size="xs" c="dimmed">关联快照：{explanation.snapshot_digest}</Text>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{explanation.text}</Text>
            <Text fw={600} size="sm">实际工具调用证据</Text>
            {explanation.tool_calls.map((call, index) => (
              <Paper key={index} withBorder p="xs">
                <Stack gap={2}>
                  <Text size="xs">{call.name} · {call.status}</Text>
                  <Text size="xs" style={{ overflowWrap: 'anywhere' }}>调用 ID：{call.tool_call_id}</Text>
                  <Text size="xs" style={{ overflowWrap: 'anywhere' }}>结果 SHA-256：{call.result_sha256}</Text>
                </Stack>
              </Paper>
            ))}
          </Stack>
        )}
        <Group>
          <Button onClick={generate} loading={state === 'generating'}
            disabled={state === 'checking' || state === 'generating' || state === 'available'}>
            生成 AI 解释
          </Button>
          <Button variant="light" onClick={() => setRefresh((value) => value + 1)}
            disabled={state === 'generating'}>
            刷新已保存解释
          </Button>
        </Group>
      </Stack>
    </Paper>
  );
}
