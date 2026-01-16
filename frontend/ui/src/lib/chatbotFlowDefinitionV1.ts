export type FlowTransitionV1 = {
  to: string;
  when?: Record<string, unknown>;
  effects?: Record<string, unknown>;
};

export type FlowNodeV1 = {
  id: string;
  type: string;
  prompt?: string;
  handler?: string;
  config?: Record<string, unknown>;
  transitions: FlowTransitionV1[];
};

export type LeadSummaryFieldV1 = {
  key: string;
  label: string;
  source: string;
  empty_value?: string | null;
};

export type LeadSummarySourceOptionV1 = {
  value: string;
  label: string;
};

export type LeadSummaryV1 = {
  fields: LeadSummaryFieldV1[];
  source_options?: LeadSummarySourceOptionV1[] | null;
};

export type LeadKanbanStageV1 = {
  id: string;
  label: string;
};

export type LeadKanbanV1 = {
  stages: LeadKanbanStageV1[];
};

export type ChatbotFlowDefinitionV1 = {
  version: number;
  start: string;
  nodes: FlowNodeV1[];
  lead_summary?: LeadSummaryV1 | null;
  lead_kanban?: LeadKanbanV1 | null;
};

export function safeJsonParse<T>(s: string): { ok: true; value: T } | { ok: false; error: string } {
  try {
    return { ok: true, value: JSON.parse(s) as T };
  } catch {
    return { ok: false, error: 'JSON inválido' };
  }
}

export function splitCommaList(raw: string): string[] {
  return (raw || '')
    .split(/[\n,]/g)
    .map((x) => x.trim())
    .filter(Boolean);
}

export function validateDefinition(def: ChatbotFlowDefinitionV1): string[] {
  const errors: string[] = [];
  const nodes = def.nodes || [];
  if (nodes.length === 0) {
    errors.push('Flow precisa ter ao menos 1 node.');
    return errors;
  }

  const ids = nodes.map((n) => (n.id || '').trim());
  const idSet = new Set(ids);

  if (ids.some((id) => !id)) errors.push('Todo node precisa ter um id.');
  if (idSet.size !== ids.length) errors.push('Existem IDs de nodes duplicados.');

  const start = (def.start || '').trim();
  if (!start) errors.push('Campo start é obrigatório.');
  if (start && !idSet.has(start)) errors.push(`Start aponta para node inexistente: ${start}`);

  for (const n of nodes) {
    const from = (n.id || '').trim();
    for (const t of n.transitions || []) {
      const to = (t.to || '').trim();
      if (!to) {
        errors.push(`Transição sem destino em node ${from || '(sem id)'}`);
      } else if (!idSet.has(to)) {
        errors.push(`Transição aponta para node inexistente: ${from || '(sem id)'} -> ${to}`);
      }
    }
  }

  return errors;
}

export function defaultDefinition(): ChatbotFlowDefinitionV1 {
  return {
    version: 1,
    start: 'start',
    nodes: [{ id: 'start', type: 'static_message', prompt: 'Olá!', transitions: [] }],
    lead_summary: {
      source_options: [
        { value: 'stage', label: 'Etapa (stage)' },
        { value: 'purpose', label: 'Finalidade (purpose)' },
        { value: 'type', label: 'Tipo (type)' },
        { value: 'city', label: 'Cidade (city)' },
        { value: 'neighborhood', label: 'Bairro (neighborhood)' },
        { value: 'bedrooms', label: 'Quartos (bedrooms)' },
        { value: 'price_min', label: 'Preço mín. (price_min)' },
        { value: 'price_max', label: 'Preço máx. (price_max)' },
        { value: 'date', label: 'Data (date)' },
        { value: 'time', label: 'Horário (time)' },
        { value: 'phone', label: 'Telefone (phone)' },
      ],
      fields: [
        { key: 'stage', label: 'Etapa', source: 'stage' },
        { key: 'city', label: 'Cidade', source: 'city' },
        { key: 'neighborhood', label: 'Bairro', source: 'neighborhood' },
      ],
    },
    lead_kanban: {
      stages: [
        { id: 'start', label: 'Início' },
        { id: 'awaiting_purpose', label: 'Finalidade' },
        { id: 'awaiting_city', label: 'Cidade' },
        { id: 'awaiting_neighborhood', label: 'Bairro' },
        { id: 'execute_search', label: 'Busca' },
      ],
    },
  };
}

export function normalizeDefinition(def: ChatbotFlowDefinitionV1): ChatbotFlowDefinitionV1 {
  const nodes = (def.nodes || []).map((n) => ({
    id: n.id,
    type: n.type,
    prompt: n.prompt,
    handler: n.handler,
    config: (n as FlowNodeV1).config,
    transitions: Array.isArray(n.transitions) ? n.transitions.map((t) => ({ to: t.to, when: t.when, effects: (t as FlowTransitionV1).effects })) : [],
  }));

  const leadSummaryFieldsRaw = (def.lead_summary?.fields || []).filter(Boolean) as LeadSummaryFieldV1[];
  const leadSummarySourceOptionsRaw = (def.lead_summary?.source_options || []).filter(Boolean) as LeadSummarySourceOptionV1[];
  const lead_summary: LeadSummaryV1 | null = {
    source_options: leadSummarySourceOptionsRaw
      .map((o) => ({
        value: (o.value || '').trim(),
        label: (o.label || '').trim(),
      }))
      .filter((o) => o.value && o.label),
    fields: leadSummaryFieldsRaw
      .map((f) => ({
        key: (f.key || '').trim(),
        label: (f.label || '').trim(),
        source: (f.source || '').trim(),
        empty_value: f.empty_value ?? null,
      }))
      .filter((f) => f.key && f.label && f.source),
  };

  const leadKanbanStagesRaw = (def.lead_kanban?.stages || []).filter(Boolean) as LeadKanbanStageV1[];
  const lead_kanban: LeadKanbanV1 | null = {
    stages: leadKanbanStagesRaw
      .map((s) => ({
        id: (s.id || '').trim(),
        label: (s.label || '').trim(),
      }))
      .filter((s) => s.id && s.label),
  };

  return {
    version: def.version || 1,
    start: def.start || (nodes[0]?.id || 'start'),
    nodes,
    lead_summary,
    lead_kanban,
  };
}

export function createNodeId(existing: FlowNodeV1[], prefix: string) {
  const base = (prefix || 'node').trim() || 'node';
  const used = new Set(existing.map((n) => n.id));
  if (!used.has(base)) return base;
  for (let i = 2; i < 999; i++) {
    const c = `${base}_${i}`;
    if (!used.has(c)) return c;
  }
  return `${base}_${Date.now()}`;
}

export function createKeyId(existing: { key: string }[], prefix: string) {
  const base = (prefix || 'field').trim() || 'field';
  const used = new Set(existing.map((x) => x.key));
  if (!used.has(base)) return base;
  for (let i = 2; i < 999; i++) {
    const c = `${base}_${i}`;
    if (!used.has(c)) return c;
  }
  return `${base}_${Date.now()}`;
}
