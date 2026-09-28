/** JSON boundaries for the plugin's owned tasks and persisted preview. */

export type Task = {
  id: string;
  status: string;
  build_ids: number[];
  updated_at: string;
};

export type Fact = string | null;

export type PreviewLine = {
  build_line_id: number;
  build_id: number;
  part_id: number;
  required: Fact;
  consumed: Fact;
  allocated: Fact;
  outstanding: Fact;
  source: { model: string; pk: number; fields: string[]; formula: string } | null;
};

export type PreviewPart = {
  part_id: number;
  name: string;
  ipn: string;
  units: string;
  build_line_ids: number[];
  selected_build_outstanding: Fact;
  available_stock: {
    value: Fact;
    source: { model: string; field: string; build_context_id: number; build_line_ids: number[] } | null;
    location_scope: string | null;
    allocation_assumption: string | null;
    warning: string | null;
  };
  preliminary_shortage: {
    value: Fact;
    source: { formula: string; build_line_ids: number[] } | null;
    warning: string | null;
  };
};

export type Preview = {
  task_id: string;
  snapshot_digest: string;
  analyzed_at: string | null;
  build: { build_id: number; reference: string; source_pk: number | null };
  lines: PreviewLine[];
  parts: PreviewPart[];
  warnings: string[];
};

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function id(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? value : null;
}

function ids(value: unknown): number[] {
  return Array.isArray(value) ? value.filter((item): item is number => id(item) !== null) : [];
}

function words(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function fact(value: unknown): Fact {
  return typeof value === 'string' && /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value)
    ? value : null;
}

export function parseBuildId(value: string): number | null {
  if (!/^[1-9][0-9]*$/.test(value)) return null;
  const buildId = id(Number(value));
  return buildId !== null && buildId <= 2147483647 ? buildId : null;
}

export function parseTask(value: unknown): Task | null {
  const item = record(value);
  if (!item || typeof item.id !== 'string' || typeof item.status !== 'string' ||
      typeof item.updated_at !== 'string' || !Array.isArray(item.build_ids) ||
      !item.build_ids.every((buildId) => id(buildId) !== null)) return null;
  return item as Task;
}

export function parseTasks(value: unknown): Task[] | null {
  const body = record(value);
  if (!body || !Array.isArray(body.tasks)) return null;
  const tasks = body.tasks.map(parseTask);
  return tasks.every((task) => task !== null) ? tasks as Task[] : null;
}

export function parseCreatedTask(value: unknown): Task | null {
  return parseTask(record(value)?.task);
}

function parseLine(value: unknown): PreviewLine | null {
  const line = record(value);
  if (!line || id(line.build_line_id) === null || id(line.build_id) === null || id(line.part_id) === null) return null;
  const source = record(line.source);
  return {
    build_line_id: id(line.build_line_id)!, build_id: id(line.build_id)!, part_id: id(line.part_id)!,
    required: fact(line.required), consumed: fact(line.consumed),
    allocated: fact(line.allocated), outstanding: fact(line.outstanding),
    source: source && typeof source.model === 'string' && id(source.pk) !== null &&
      typeof source.formula === 'string'
      ? { model: source.model, pk: id(source.pk)!, fields: words(source.fields), formula: source.formula }
      : null
  };
}

function parsePart(value: unknown): PreviewPart | null {
  const part = record(value);
  if (!part || id(part.part_id) === null) return null;
  const stock = record(part.available_stock);
  const shortage = record(part.preliminary_shortage);
  const stockSource = record(stock?.source);
  const shortageSource = record(shortage?.source);
  const location = record(stock?.location_assumption);
  return {
    part_id: id(part.part_id)!, name: typeof part.name === 'string' ? part.name : '待核实',
    ipn: typeof part.ipn === 'string' ? part.ipn : '待核实',
    units: typeof part.units === 'string' ? part.units : '待核实',
    build_line_ids: ids(part.build_line_ids),
    selected_build_outstanding: fact(part.selected_build_outstanding),
    available_stock: {
      value: fact(stock?.value),
      source: stockSource && typeof stockSource.model === 'string' &&
        typeof stockSource.field === 'string' && id(stockSource.build_context_id) !== null
        ? { model: stockSource.model, field: stockSource.field,
            build_context_id: id(stockSource.build_context_id)!, build_line_ids: ids(stockSource.build_line_ids) }
        : null,
      location_scope: typeof location?.scope === 'string' ? location.scope : null,
      allocation_assumption: typeof stock?.allocation_assumption === 'string'
        ? stock.allocation_assumption : null,
      warning: typeof stock?.warning === 'string' ? stock.warning : null
    },
    preliminary_shortage: {
      value: fact(shortage?.value),
      source: shortageSource && typeof shortageSource.formula === 'string'
        ? { formula: shortageSource.formula, build_line_ids: ids(shortageSource.build_line_ids) }
        : null,
      warning: typeof shortage?.warning === 'string' ? shortage.warning : null
    }
  };
}

export function parsePreview(value: unknown): Preview | null {
  const body = record(value);
  const preview = record(body?.preview);
  const build = record(preview?.build);
  if (!body || typeof body.task_id !== 'string' || typeof body.snapshot_digest !== 'string' ||
      !preview || preview.schema_version !== 1 || !build || id(build.build_id) === null ||
      !Array.isArray(preview.lines) || !Array.isArray(preview.parts)) return null;
  const lines = preview.lines.map(parseLine);
  const parts = preview.parts.map(parsePart);
  if (lines.some((line) => line === null) || parts.some((part) => part === null)) return null;
  return {
    task_id: body.task_id,
    snapshot_digest: body.snapshot_digest,
    analyzed_at: typeof body.analyzed_at === 'string' ? body.analyzed_at : null,
    build: { build_id: id(build.build_id)!, reference: typeof build.reference === 'string' ? build.reference : '待核实',
      source_pk: id(record(build.source)?.pk) },
    lines: lines as PreviewLine[], parts: parts as PreviewPart[], warnings: words(preview.warnings)
  };
}

export function displayFact(value: Fact): string {
  return value === null ? '待核实' : value;
}

export function requestError(error: unknown): string {
  const response = record(record(error)?.response);
  const status = response?.status;
  if (status === 400) return '请求格式有误，请检查生产单 ID。';
  if (status === 401) return '登录已失效，请重新登录后重试。';
  if (status === 403) return '没有读取生产单、物料或库存所需的权限。';
  if (status === 404) return '生产单或任务不存在，或当前用户无法访问。';
  if (status === 409) return '预览尚未生成，请稍后刷新。';
  return '请求失败，请检查连接后重试。';
}
