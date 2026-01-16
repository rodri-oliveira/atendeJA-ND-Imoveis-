import {
  type ChatbotFlowDefinitionV1,
  type FlowNodeV1,
  type FlowTransitionV1,
  type LeadKanbanStageV1,
  type LeadSummaryFieldV1,
  type LeadSummarySourceOptionV1,
  createKeyId,
  normalizeDefinition,
} from './chatbotFlowDefinitionV1';

export type RemoveNodeResult = {
  definition: ChatbotFlowDefinitionV1;
  nextSelectedNodeId: string;
};

export function removeNodeFromDefinition(def: ChatbotFlowDefinitionV1, nodeId: string): RemoveNodeResult {
  const next = normalizeDefinition(def);
  const targetId = (nodeId || '').trim();

  const remaining = (next.nodes || []).filter((x) => x.id !== targetId);
  const start = next.start === targetId ? (remaining[0]?.id || 'start') : next.start;
  const cleaned = remaining.map((x) => ({
    ...x,
    transitions: (x.transitions || []).filter((t) => t.to !== targetId),
  }));

  return {
    definition: { ...next, start, nodes: cleaned },
    nextSelectedNodeId: start,
  };
}

export type RenameNodeResult = {
  definition: ChatbotFlowDefinitionV1;
  nextSelectedNodeId: string;
};

export function renameNodeInDefinition(def: ChatbotFlowDefinitionV1, fromId: string, toId: string): RenameNodeResult {
  const next = normalizeDefinition(def);
  const src = (fromId || '').trim();
  const dst = (toId || '').trim();

  const nodes = (next.nodes || []).map((x) => {
    if (x.id !== src) {
      return {
        ...x,
        transitions: (x.transitions || []).map((t) => (t.to === src ? { ...t, to: dst } : t)),
      };
    }
    return { ...x, id: dst };
  });

  const start = next.start === src ? dst : next.start;
  return { definition: { ...next, start, nodes }, nextSelectedNodeId: dst };
}

export function addTransitionToNode(def: ChatbotFlowDefinitionV1, nodeIdx: number, to: string): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const toId = (to || '').trim();
  if (!Number.isFinite(nodeIdx) || nodeIdx < 0) return next;

  return {
    ...next,
    nodes: (next.nodes || []).map((x, i) => {
      if (i !== nodeIdx) return x;
      const transitions = [...(x.transitions || [])];
      transitions.push({ to: toId } as FlowTransitionV1);
      return { ...x, transitions };
    }),
  };
}

export function removeTransitionFromNode(def: ChatbotFlowDefinitionV1, nodeIdx: number, tIdx: number): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  if (!Number.isFinite(nodeIdx) || nodeIdx < 0) return next;
  if (!Number.isFinite(tIdx) || tIdx < 0) return next;

  return {
    ...next,
    nodes: (next.nodes || []).map((x, i) => {
      if (i !== nodeIdx) return x;
      const transitions = [...(x.transitions || [])];
      transitions.splice(tIdx, 1);
      return { ...x, transitions };
    }),
  };
}

export function updateTransitionInDefinition(
  def: ChatbotFlowDefinitionV1,
  nodeIdx: number,
  tIdx: number,
  patch: Partial<FlowTransitionV1>,
): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  if (!Number.isFinite(nodeIdx) || nodeIdx < 0) return next;
  if (!Number.isFinite(tIdx) || tIdx < 0) return next;

  return {
    ...next,
    nodes: (next.nodes || []).map((x, i) => {
      if (i !== nodeIdx) return x;
      const transitions = (x.transitions || []).map((tt, j) => (j === tIdx ? { ...tt, ...patch } : tt));
      return { ...x, transitions };
    }),
  };
}

export function setTransitionWhenInDefinition(
  def: ChatbotFlowDefinitionV1,
  nodeIdx: number,
  tIdx: number,
  nextWhen: Record<string, unknown> | undefined,
): ChatbotFlowDefinitionV1 {
  const when = nextWhen && Object.keys(nextWhen).length > 0 ? nextWhen : undefined;
  return updateTransitionInDefinition(def, nodeIdx, tIdx, { when });
}

export function updateNodeInDefinition(def: ChatbotFlowDefinitionV1, nodeIdx: number, patch: Partial<FlowNodeV1>): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  if (!Number.isFinite(nodeIdx) || nodeIdx < 0) return next;

  return {
    ...next,
    nodes: (next.nodes || []).map((x, i) => (i === nodeIdx ? { ...x, ...patch } : x)),
  };
}

export function getNodeConfig(node: FlowNodeV1): Record<string, unknown> {
  if (!node.config || typeof node.config !== 'object') return {};
  return node.config as Record<string, unknown>;
}

export function updateNodeConfigValueInDefinition(
  def: ChatbotFlowDefinitionV1,
  nodeIdx: number,
  key: string,
  value: unknown,
): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  if (!Number.isFinite(nodeIdx) || nodeIdx < 0) return next;

  const nodes = (next.nodes || []).map((x, i) => {
    if (i !== nodeIdx) return x;
    const base = x.config && typeof x.config === 'object' ? (x.config as Record<string, unknown>) : {};
    const cfg: Record<string, unknown> = { ...base };

    const shouldDelete = value === undefined || value === null || value === '';
    if (shouldDelete) {
      delete cfg[key];
    } else {
      cfg[key] = value;
    }

    const hasAny = Object.keys(cfg).length > 0;
    return { ...x, config: hasAny ? cfg : undefined };
  });

  return { ...next, nodes };
}

export function updateLeadSummarySourceOptionInDefinition(
  def: ChatbotFlowDefinitionV1,
  idx: number,
  patch: Partial<LeadSummarySourceOptionV1>,
): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const fields = Array.isArray(next.lead_summary?.fields) ? [...next.lead_summary!.fields] : [];
  const opts = Array.isArray(next.lead_summary?.source_options) ? [...next.lead_summary!.source_options!] : [];
  const cur = opts[idx];
  if (!cur) return next;
  opts[idx] = { ...cur, ...patch };
  return { ...next, lead_summary: { fields, source_options: opts } };
}

export function addLeadSummarySourceOptionToDefinition(def: ChatbotFlowDefinitionV1): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const fields = Array.isArray(next.lead_summary?.fields) ? [...next.lead_summary!.fields] : [];
  const opts = Array.isArray(next.lead_summary?.source_options) ? [...next.lead_summary!.source_options!] : [];
  opts.push({ value: 'custom', label: 'Personalizado (custom)' });
  return { ...next, lead_summary: { fields, source_options: opts } };
}

export function removeLeadSummarySourceOptionFromDefinition(def: ChatbotFlowDefinitionV1, idx: number): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const fields = Array.isArray(next.lead_summary?.fields) ? [...next.lead_summary!.fields] : [];
  const opts = Array.isArray(next.lead_summary?.source_options) ? [...next.lead_summary!.source_options!] : [];
  opts.splice(idx, 1);
  return { ...next, lead_summary: { fields, source_options: opts } };
}

export function moveLeadSummarySourceOptionInDefinition(def: ChatbotFlowDefinitionV1, idx: number, dir: -1 | 1): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const fields = Array.isArray(next.lead_summary?.fields) ? [...next.lead_summary!.fields] : [];
  const opts = Array.isArray(next.lead_summary?.source_options) ? [...next.lead_summary!.source_options!] : [];
  const nextIdx = idx + dir;
  if (idx < 0 || idx >= opts.length) return next;
  if (nextIdx < 0 || nextIdx >= opts.length) return next;
  const tmp = opts[idx];
  opts[idx] = opts[nextIdx]!;
  opts[nextIdx] = tmp!;
  return { ...next, lead_summary: { fields, source_options: opts } };
}

export function updateLeadSummaryFieldInDefinition(
  def: ChatbotFlowDefinitionV1,
  idx: number,
  patch: Partial<LeadSummaryFieldV1>,
): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const fields = Array.isArray(next.lead_summary?.fields) ? [...next.lead_summary!.fields] : [];
  const source_options = Array.isArray(next.lead_summary?.source_options) ? [...next.lead_summary!.source_options!] : undefined;
  const cur = fields[idx];
  if (!cur) return next;
  fields[idx] = { ...cur, ...patch };
  return { ...next, lead_summary: { fields, source_options } };
}

export function addLeadSummaryFieldToDefinition(def: ChatbotFlowDefinitionV1): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const fields = Array.isArray(next.lead_summary?.fields) ? [...next.lead_summary!.fields] : [];
  const source_options = Array.isArray(next.lead_summary?.source_options) ? [...next.lead_summary!.source_options!] : undefined;
  const key = createKeyId(fields, 'field');
  fields.push({ key, label: 'Novo campo', source: 'stage', empty_value: null });
  return { ...next, lead_summary: { fields, source_options } };
}

export function removeLeadSummaryFieldFromDefinition(def: ChatbotFlowDefinitionV1, idx: number): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const fields = Array.isArray(next.lead_summary?.fields) ? [...next.lead_summary!.fields] : [];
  const source_options = Array.isArray(next.lead_summary?.source_options) ? [...next.lead_summary!.source_options!] : undefined;
  fields.splice(idx, 1);
  return { ...next, lead_summary: { fields, source_options } };
}

export function moveLeadSummaryFieldInDefinition(def: ChatbotFlowDefinitionV1, idx: number, dir: -1 | 1): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const fields = Array.isArray(next.lead_summary?.fields) ? [...next.lead_summary!.fields] : [];
  const source_options = Array.isArray(next.lead_summary?.source_options) ? [...next.lead_summary!.source_options!] : undefined;
  const nextIdx = idx + dir;
  if (idx < 0 || idx >= fields.length) return next;
  if (nextIdx < 0 || nextIdx >= fields.length) return next;
  const tmp = fields[idx];
  fields[idx] = fields[nextIdx]!;
  fields[nextIdx] = tmp!;
  return { ...next, lead_summary: { fields, source_options } };
}

export function updateLeadKanbanStageInDefinition(
  def: ChatbotFlowDefinitionV1,
  idx: number,
  patch: Partial<LeadKanbanStageV1>,
): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const stages = Array.isArray(next.lead_kanban?.stages) ? [...next.lead_kanban!.stages] : [];
  const cur = stages[idx];
  if (!cur) return next;
  stages[idx] = { ...cur, ...patch };
  return { ...next, lead_kanban: { stages } };
}

export function addLeadKanbanStageToDefinition(def: ChatbotFlowDefinitionV1): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const stages = Array.isArray(next.lead_kanban?.stages) ? [...next.lead_kanban!.stages] : [];
  const used = new Set(stages.map((s) => s.id));
  const candidates = (next.nodes || []).map((n) => n.id).filter((id) => !used.has(id));
  const id = candidates[0] || 'start';
  stages.push({ id, label: id });
  return { ...next, lead_kanban: { stages } };
}

export function removeLeadKanbanStageFromDefinition(def: ChatbotFlowDefinitionV1, idx: number): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const stages = Array.isArray(next.lead_kanban?.stages) ? [...next.lead_kanban!.stages] : [];
  stages.splice(idx, 1);
  return { ...next, lead_kanban: { stages } };
}

export function moveLeadKanbanStageInDefinition(def: ChatbotFlowDefinitionV1, idx: number, dir: -1 | 1): ChatbotFlowDefinitionV1 {
  const next = normalizeDefinition(def);
  const stages = Array.isArray(next.lead_kanban?.stages) ? [...next.lead_kanban!.stages] : [];
  const nextIdx = idx + dir;
  if (idx < 0 || idx >= stages.length) return next;
  if (nextIdx < 0 || nextIdx >= stages.length) return next;
  const tmp = stages[idx];
  stages[idx] = stages[nextIdx]!;
  stages[nextIdx] = tmp!;
  return { ...next, lead_kanban: { stages } };
}
