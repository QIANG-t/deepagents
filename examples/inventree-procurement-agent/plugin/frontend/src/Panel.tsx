import type { InvenTreePluginContext } from '@inventreedb/ui';
import { Alert, Badge, Button, Group, Loader, Paper, Stack, Text, Title } from '@mantine/core';
import * as React from 'react';

const HEALTH_URL = '/plugin/inventree_procurement/health/';
const TASKS_URL = '/plugin/inventree_procurement/tasks/';

type LoadState = 'checking' | 'available' | 'unavailable';
type Task = { id: string; status: string; build_ids: number[]; updated_at: string };

function parseTasks(data: unknown): Task[] | null {
  if (!data || typeof data !== 'object' || !('tasks' in data)) return null;
  const tasks = data.tasks;
  if (!Array.isArray(tasks)) return null;
  if (!tasks.every((task) =>
    task && typeof task.id === 'string' && typeof task.status === 'string' &&
    Array.isArray(task.build_ids) && task.build_ids.every(Number.isInteger) &&
    typeof task.updated_at === 'string'
  )) return null;
  return tasks as Task[];
}

function ProcurementPanel({ context }: { context: InvenTreePluginContext }) {
  const [health, setHealth] = React.useState<LoadState>('checking');
  const [taskState, setTaskState] = React.useState<LoadState>('checking');
  const [tasks, setTasks] = React.useState<Task[]>([]);
  const [refresh, setRefresh] = React.useState(0);

  React.useEffect(() => {
    const controller = new AbortController();
    setHealth('checking');
    setTaskState('checking');
    setTasks([]);

    context.api
      .get<unknown>(HEALTH_URL, { signal: controller.signal })
      .then(async ({ data }) => {
        if (controller.signal.aborted) return;
        const response = data as { status?: unknown } | null;
        if (response?.status !== 'ok') {
          setHealth('unavailable');
          setTaskState('unavailable');
          return;
        }
        setHealth('available');
        try {
          const taskResponse = await context.api.get<unknown>(TASKS_URL, { signal: controller.signal });
          if (controller.signal.aborted) return;
          const parsed = parseTasks(taskResponse.data);
          if (parsed === null) {
            setTaskState('unavailable');
          } else {
            setTasks(parsed);
            setTaskState('available');
          }
        } catch {
          if (!controller.signal.aborted) setTaskState('unavailable');
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setHealth('unavailable');
          setTaskState('unavailable');
        }
      });

    return () => controller.abort();
  }, [context.api, refresh]);

  const healthLabel = health === 'available' ? 'Available' : health === 'checking' ? 'Checking' : 'Unavailable';

  return (
    <Paper withBorder p="md" radius="md">
      <Stack gap="md">
        <Group justify="space-between" align="start">
          <div>
            <Title order={3}>Procurement tasks</Title>
            <Text size="sm" c="dimmed">Read-only integration preview</Text>
          </div>
          <Badge color={health === 'available' ? 'green' : health === 'checking' ? 'gray' : 'red'}>
            {healthLabel}
          </Badge>
        </Group>

        {health === 'checking' && <Loader size="sm" aria-label="Checking plugin health" />}
        {health === 'unavailable' && (
          <Alert color="yellow" title="Plugin service unavailable">
            Health could not be confirmed. Check the plugin endpoint and your access.
          </Alert>
        )}
        <Stack gap={4}>
          <Text fw={600}>Task status</Text>
          {taskState === 'checking' && <Text size="sm" c="dimmed">Loading owned tasks…</Text>}
          {taskState === 'unavailable' && <Text size="sm" c="dimmed">Task list is unavailable.</Text>}
          {taskState === 'available' && tasks.length === 0 &&
            <Text size="sm" c="dimmed">No tasks found for this account.</Text>}
          {taskState === 'available' && tasks.map((task) => (
            <Paper key={task.id} withBorder p="xs">
              <Group justify="space-between">
                <Text size="sm" fw={600}>{task.id}</Text>
                <Badge variant="light">{task.status}</Badge>
              </Group>
              <Text size="xs" c="dimmed">
                Build IDs: {task.build_ids.length ? task.build_ids.join(', ') : 'none'}
              </Text>
              <Text size="xs" c="dimmed">Updated: {task.updated_at}</Text>
            </Paper>
          ))}
        </Stack>
        <Stack gap={4}>
          <Text fw={600}>Data sources</Text>
          <Text size="sm" c="dimmed">
            Task records: {taskState === 'available' ? 'plugin task API' : 'unavailable'}.
            {' '}Build details, stock, supplier parts, and quote documents: not connected.
          </Text>
        </Stack>
        <Group>
          <Button variant="light" size="xs" onClick={() => setRefresh((value) => value + 1)}>
            Refresh health
          </Button>
        </Group>
      </Stack>
    </Paper>
  );
}

/** Entrypoint referenced by UserInterfaceMixin's plugin_static_file(...). */
export function RenderProcurementPanel(context: InvenTreePluginContext) {
  return <ProcurementPanel context={context} />;
}
