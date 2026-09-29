import type { InvenTreePluginContext } from '@inventreedb/ui';
import { Alert, Button, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core';
import * as React from 'react';
import { displayFact, parseDecisionPreview, requestError, responseCode, responseStatus } from './contracts';
import type { DecisionPreview } from './contracts';

type State = 'checking' | 'unavailable' | 'available' | 'error';

export function DecisionPreviewPanel({ context, taskId, snapshotDigest }: {
  context: InvenTreePluginContext;
  taskId: string;
  snapshotDigest: string;
}) {
  const [state, setState] = React.useState<State>('checking');
  const [preview, setPreview] = React.useState<DecisionPreview | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [refresh, setRefresh] = React.useState(0);
  const url = `/plugin/inventree_procurement/tasks/${encodeURIComponent(taskId)}/decision-preview/`;

  React.useEffect(() => {
    const controller = new AbortController();
    setState('checking');
    setPreview(null);
    setError(null);
    context.api.get<unknown>(url, { signal: controller.signal })
      .then(({ data }) => {
        if (controller.signal.aborted) return;
        const parsed = parseDecisionPreview(data);
        if (!parsed || parsed.task_id !== taskId || parsed.snapshot_digest !== snapshotDigest) {
          setError('决策预览格式或生产单快照无法核对，请刷新任务预览。');
          setState('error');
          return;
        }
        setPreview(parsed);
        setState('available');
      })
      .catch((failure) => {
        if (controller.signal.aborted) return;
        if (responseStatus(failure) === 409 && responseCode(failure) === 'decision_preview_unavailable') {
          setState('unavailable');
        } else {
          setError(requestError(failure));
          setState('error');
        }
      });
    return () => controller.abort();
  }, [context.api, url, taskId, snapshotDigest, refresh]);

  return (
    <Paper withBorder p="md" radius="md">
      <Stack gap="sm">
        <Title order={4}>采购决策预览（只读）</Title>
        <Text size="sm" c="dimmed">这里只整理缺口、报价和需要人工核实的问题。当前没有可下单数量或估算总价，也不会创建采购单。</Text>
        {state === 'checking' && <Loader size="sm" aria-label="加载采购决策预览" />}
        {state === 'unavailable' && <Text size="sm" c="dimmed">生产单预览尚未生成，请刷新任务后再查看。</Text>}
        {state === 'error' && <Alert color="yellow">{error}</Alert>}
        {state === 'available' && preview && <Stack gap="sm">
          <Text size="xs" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
            生产单快照：{preview.snapshot_digest} · 报价原文：{preview.quote_source_sha256 ?? '未关联'}
          </Text>
          {preview.rows.length === 0 && <Text size="sm" c="dimmed">暂无物料行。</Text>}
          {preview.rows.map((row) => (
            <Paper key={row.part_id} withBorder p="sm">
              <Stack gap="xs">
                <Text fw={600}>Part {row.part_id} · {row.name}</Text>
                <Group gap="md">
                  <Text size="sm">初步缺口：{displayFact(row.preliminary_shortage)} {row.units}</Text>
                  <Text size="sm">SupplierPart：{row.supplier_part_id ?? '未关联'}</Text>
                </Group>
                <Text size="sm">报价单价：{displayFact(row.quote_unit_price)} {row.quote_currency ?? ''} / {row.quote_price_unit ?? '待核实'}</Text>
                <Text size="sm">可下单数量：待核实 · 估算总价：待核实</Text>
                {row.blockers.map((blocker, index) => (
                  <Alert key={`${blocker.code}-${index}`} color="yellow" title="需人工核实">{blocker.message}</Alert>
                ))}
              </Stack>
            </Paper>
          ))}
        </Stack>}
        <Button variant="light" onClick={() => setRefresh((value) => value + 1)}>刷新决策预览</Button>
      </Stack>
    </Paper>
  );
}
