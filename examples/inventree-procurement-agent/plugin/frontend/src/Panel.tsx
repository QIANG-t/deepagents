import type { InvenTreePluginContext } from '@inventreedb/ui';
import { Alert, Badge, Button, Group, Loader, Paper, Stack, Text, TextInput, Title } from '@mantine/core';
import * as React from 'react';
import { displayFact, parseBuildId, parseCreatedTask, parsePreview, parseTasks, requestError } from './contracts';
import type { Preview, PreviewLine, PreviewPart, Task } from './contracts';
import { ExplanationPanel } from './ExplanationPanel';
import { QuotePanel } from './QuotePanel';

const BASE_URL = '/plugin/inventree_procurement/';
type LoadState = 'idle' | 'checking' | 'available' | 'unavailable';

function PreviewFacts({ line }: { line: PreviewLine }) {
  const facts = [
    ['需求量', line.required], ['已消耗', line.consumed], ['已分配', line.allocated],
    ['未满足需求', line.outstanding]
  ] as const;
  return (
    <Paper withBorder p="sm">
      <Stack gap="xs">
        <Text fw={600}>BuildLine {line.build_line_id} · Part {line.part_id}</Text>
        <Group gap="md">{facts.map(([label, value]) => (
          <Text key={label} size="sm">{label}：{displayFact(value)}</Text>
        ))}</Group>
        <Text size="xs" c="dimmed">
          来源：{line.source ? `${line.source.model} #${line.source.pk}；${line.source.fields.join(', ')}` : '待核实'}
        </Text>
        <Text size="xs" c="dimmed">计算：{line.source?.formula ?? '待核实'}</Text>
      </Stack>
    </Paper>
  );
}

function PartFacts({ part }: { part: PreviewPart }) {
  const stock = part.available_stock;
  const shortage = part.preliminary_shortage;
  return (
    <Paper withBorder p="sm">
      <Stack gap="xs">
        <Text fw={600}>Part {part.part_id} · {part.name} ({part.ipn})</Text>
        <Text size="sm">关联 BuildLine：{part.build_line_ids.join(', ') || '待核实'}</Text>
        <Group gap="md">
          <Text size="sm">选中生产单未满足需求：{displayFact(part.selected_build_outstanding)} {part.units}</Text>
          <Text size="sm">可用库存：{displayFact(stock.value)} {part.units}</Text>
          <Text size="sm">初步缺口：{displayFact(shortage.value)} {part.units}</Text>
        </Group>
        <Text size="xs" c="dimmed">
          库存来源：{stock.source ? `${stock.source.model}.${stock.source.field}；生产单 ${stock.source.build_context_id}；BuildLine ${stock.source.build_line_ids.join(', ')}` : '待核实'}
        </Text>
        <Text size="xs" c="dimmed">位置范围：{stock.location_scope ?? '待核实'}</Text>
        <Text size="xs" c="dimmed">分配口径：{stock.allocation_assumption ?? '待核实'}</Text>
        <Text size="xs" c="dimmed">
          缺口依据：{shortage.source ? `${shortage.source.formula}；BuildLine ${shortage.source.build_line_ids.join(', ')}` : '待核实'}
        </Text>
        {stock.warning && <Alert color="yellow">{stock.warning}</Alert>}
        {shortage.warning && <Alert color="yellow">{shortage.warning}</Alert>}
      </Stack>
    </Paper>
  );
}

function PreviewContent({ preview }: { preview: Preview }) {
  return (
    <Stack gap="sm">
      <Text size="sm">生产单：{preview.build.reference}（ID {preview.build.build_id}；来源 Build #{preview.build.source_pk ?? '待核实'}）</Text>
      <Text size="xs" c="dimmed">快照摘要：{preview.snapshot_digest} · 分析时间：{preview.analyzed_at ?? '待核实'}</Text>
      {preview.warnings.map((warning, index) => (
        <Alert key={index} color="yellow">{warning}</Alert>
      ))}
      {preview.lines.length === 0 && <Text size="sm" c="dimmed">此任务暂无物料需求行。</Text>}
      {preview.lines.map((line) => <PreviewFacts key={line.build_line_id} line={line} />)}
      {preview.parts.length > 0 && <Text fw={600}>按 Part 汇总的库存与初步缺口（库存仅计一次）</Text>}
      {preview.parts.map((part) => <PartFacts key={part.part_id} part={part} />)}
    </Stack>
  );
}

function ProcurementPanel({ context }: { context: InvenTreePluginContext }) {
  const [health, setHealth] = React.useState<LoadState>('checking');
  const [taskState, setTaskState] = React.useState<LoadState>('checking');
  const [tasks, setTasks] = React.useState<Task[]>([]);
  const [buildInput, setBuildInput] = React.useState('');
  const [creating, setCreating] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);
  const [creationUncertain, setCreationUncertain] = React.useState(false);
  const [selectedTask, setSelectedTask] = React.useState<string | null>(null);
  const [previewState, setPreviewState] = React.useState<LoadState>('idle');
  const [preview, setPreview] = React.useState<Preview | null>(null);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [refresh, setRefresh] = React.useState(0);
  const [previewRefresh, setPreviewRefresh] = React.useState(0);
  const createLock = React.useRef(false);

  React.useEffect(() => {
    const controller = new AbortController();
    setHealth('checking');
    setTaskState('checking');
    setCreateError(null);
    context.api.get<unknown>(`${BASE_URL}health/`, { signal: controller.signal })
      .then(async ({ data }) => {
        if (controller.signal.aborted) return;
        const healthy = data !== null && typeof data === 'object' &&
          'status' in data && data.status === 'ok';
        if (!healthy) {
          setHealth('unavailable');
          setTaskState('unavailable');
          return;
        }
        setHealth('available');
        try {
          const response = await context.api.get<unknown>(`${BASE_URL}tasks/`, { signal: controller.signal });
          if (controller.signal.aborted) return;
          const loaded = parseTasks(response.data);
          if (loaded === null) {
            setTaskState('unavailable');
          } else {
            setTasks(loaded);
            setTaskState('available');
            setCreationUncertain(false);
          }
        } catch (error) {
          if (!controller.signal.aborted) {
            setTaskState('unavailable');
            setCreateError(requestError(error));
          }
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setHealth('unavailable');
          setTaskState('unavailable');
          setCreateError(requestError(error));
        }
      });
    return () => controller.abort();
  }, [context.api, refresh]);

  React.useEffect(() => {
    if (!selectedTask) {
      setPreviewState('idle');
      setPreview(null);
      return;
    }
    const controller = new AbortController();
    setPreviewState('checking');
    setPreview(null);
    setPreviewError(null);
    context.api.get<unknown>(`${BASE_URL}tasks/${encodeURIComponent(selectedTask)}/preview/`,
      { signal: controller.signal })
      .then(({ data }) => {
        if (controller.signal.aborted) return;
        const loaded = parsePreview(data);
        if (loaded === null || loaded.task_id !== selectedTask) {
          setPreviewState('unavailable');
          setPreviewError('预览响应格式无法识别，请核对插件版本。');
        } else {
          setPreview(loaded);
          setPreviewState('available');
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setPreviewState('unavailable');
          setPreviewError(requestError(error));
        }
      });
    return () => controller.abort();
  }, [context.api, selectedTask, previewRefresh]);

  const buildId = parseBuildId(buildInput);

  async function createTask() {
    if (createLock.current || buildId === null || health !== 'available' ||
        taskState !== 'available' || creationUncertain) return;
    createLock.current = true;
    setCreating(true);
    setCreateError(null);
    try {
      const response = await context.api.post<unknown>(`${BASE_URL}tasks/`, { build_ids: [buildId] });
      const created = parseCreatedTask(response.data);
      if (created === null) {
        setCreationUncertain(true);
        setCreateError('任务可能已创建，但响应格式无法识别。请先刷新任务列表核对。');
        return;
      }
      const detail = await context.api.get<unknown>(`${BASE_URL}tasks/${encodeURIComponent(created.id)}/`);
      const persisted = parseCreatedTask(detail.data);
      if (persisted === null || persisted.id !== created.id) {
        setCreationUncertain(true);
        setCreateError('任务已创建，但回查结果无法核对。请刷新任务列表后再继续。');
        return;
      }
      setTasks((current) => [persisted, ...current.filter((task) => task.id !== persisted.id)]);
      setSelectedTask(persisted.id);
      setBuildInput('');
    } catch (error) {
      setCreationUncertain(true);
      setCreateError(`${requestError(error)} 请先刷新任务列表核对，勿重复提交。`);
    } finally {
      createLock.current = false;
      setCreating(false);
    }
  }

  return (
    <Paper withBorder p="md" radius="md">
      <Stack gap="md">
        <Group justify="space-between" align="start">
          <div>
            <Title order={3}>采购分析任务</Title>
            <Text size="sm" c="dimmed">只读预览；不会创建采购单或发起审批。</Text>
          </div>
          <Badge color={health === 'available' ? 'green' : health === 'checking' ? 'gray' : 'red'}>
            {health === 'available' ? '插件可用' : health === 'checking' ? '检查中' : '插件不可用'}
          </Badge>
        </Group>

        {health === 'checking' && <Loader size="sm" aria-label="检查插件状态" />}
        {health === 'unavailable' && <Alert color="yellow">无法确认插件服务状态。</Alert>}
        <Group align="end">
          <TextInput label="生产单 ID" inputMode="numeric" value={buildInput}
            onChange={(event) => setBuildInput(event.currentTarget.value)}
            error={buildInput && buildId === null ? '请输入一个正整数 ID。' : undefined}
            placeholder="例如 123" />
          <Button onClick={createTask} loading={creating}
            disabled={buildId === null || health !== 'available' || taskState !== 'available' || creationUncertain}>
            创建分析任务
          </Button>
        </Group>
        {createError && <Alert color="yellow">{createError}</Alert>}

        <Stack gap="xs">
          <Text fw={600}>任务状态</Text>
          {taskState === 'checking' && <Text size="sm" c="dimmed">正在加载任务…</Text>}
          {taskState === 'unavailable' && <Text size="sm" c="dimmed">任务列表不可用。</Text>}
          {taskState === 'available' && tasks.length === 0 && <Text size="sm" c="dimmed">当前账户暂无任务。</Text>}
          {taskState === 'available' && tasks.map((task) => (
            <Paper key={task.id} withBorder p="xs">
              <Group justify="space-between">
                <Text size="sm" fw={600}>{task.id}</Text>
                <Badge variant="light">{task.status}</Badge>
              </Group>
              <Text size="xs" c="dimmed">生产单 ID：{task.build_ids.join(', ') || '待核实'} · 更新于 {task.updated_at}</Text>
              <Button size="xs" variant="subtle" onClick={() => setSelectedTask(task.id)}>
                查看只读预览
              </Button>
            </Paper>
          ))}
        </Stack>

        <Stack gap="xs">
          <Group justify="space-between">
            <Text fw={600}>物料需求与库存预览</Text>
            {selectedTask && <Button size="xs" variant="light" onClick={() => setPreviewRefresh((value) => value + 1)}>
              刷新预览
            </Button>}
          </Group>
          {!selectedTask && <Text size="sm" c="dimmed">选择任务后读取预览。</Text>}
          {previewState === 'checking' && <Loader size="sm" aria-label="加载预览" />}
          {previewState === 'unavailable' && <Alert color="yellow">{previewError}</Alert>}
          {previewState === 'available' && preview && <PreviewContent preview={preview} />}
          {previewState === 'available' && preview && selectedTask &&
            <ExplanationPanel key={selectedTask} context={context} taskId={selectedTask}
              snapshotDigest={preview.snapshot_digest} />}
          {previewState === 'available' && preview && selectedTask &&
            <QuotePanel key={`quote-${selectedTask}`} context={context} taskId={selectedTask} />}
        </Stack>

        <Text size="xs" c="dimmed">
          数据来源：插件任务、BuildLine、Part 与已关联 SupplierPart 的只读接口。报价原文需人工粘贴；采购执行尚未接入。
        </Text>
        <Button variant="light" size="xs" onClick={() => setRefresh((value) => value + 1)}>
          刷新任务列表
        </Button>
      </Stack>
    </Paper>
  );
}

/** Entrypoint referenced by UserInterfaceMixin's plugin_static_file(...). */
export function RenderProcurementPanel(context: InvenTreePluginContext) {
  return <ProcurementPanel context={context} />;
}
