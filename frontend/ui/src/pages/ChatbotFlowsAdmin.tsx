import React, { useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../lib/auth';

// Types matching the backend schema
type FlowTransitionV1 = {
  to: string;
  when?: Record<string, unknown>;
};

type FlowNodeV1 = {
  id: string;
  type: string;
  prompt?: string;
  handler?: string;
  transitions: FlowTransitionV1[];
};

type LeadSummaryFieldV1 = {
  key: string;
  label: string;
  source: string;
  empty_value?: string | null;
};

type LeadSummarySourceOptionV1 = {
  value: string;
  label: string;
};

type LeadSummaryV1 = {
  fields: LeadSummaryFieldV1[];
  source_options?: LeadSummarySourceOptionV1[] | null;
};

type LeadKanbanStageV1 = {
  id: string;
  label: string;
};

type LeadKanbanV1 = {
  stages: LeadKanbanStageV1[];
};

type ChatbotFlowDefinitionV1 = {
  version: number;
  start: string;
  nodes: FlowNodeV1[];
  lead_summary?: LeadSummaryV1 | null;
  lead_kanban?: LeadKanbanV1 | null;
};

type FlowEditorMode = 'guided' | 'json';

const FLOW_NODE_TYPES = [
  'static_message',
  'end',
  'handler',
  'prompt_and_branch',
  'capture_phone',
  'capture_date',
  'capture_time',
  'capture_purpose',
  'capture_property_type',
  'capture_price_min',
  'capture_price_max',
  'capture_bedrooms',
  'capture_city',
  'capture_neighborhood',
  'execute_search',
  'show_property_card',
  'property_feedback_decision',
  'refinement_decision',
] as const;

type FlowNodeType = (typeof FLOW_NODE_TYPES)[number];

function safeJsonParse<T>(s: string): { ok: true; value: T } | { ok: false; error: string } {
  try {
    return { ok: true, value: JSON.parse(s) as T };
  } catch {
    return { ok: false, error: 'JSON inválido' };
  }
}

function validateDefinition(def: ChatbotFlowDefinitionV1): string[] {
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

function defaultDefinition(): ChatbotFlowDefinitionV1 {
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

function normalizeDefinition(def: ChatbotFlowDefinitionV1): ChatbotFlowDefinitionV1 {
  const nodes = (def.nodes || []).map((n) => ({
    id: n.id,
    type: n.type,
    prompt: n.prompt,
    handler: n.handler,
    transitions: Array.isArray(n.transitions) ? n.transitions.map((t) => ({ to: t.to, when: t.when })) : [],
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

function createNodeId(existing: FlowNodeV1[], prefix: string) {
  const base = (prefix || 'node').trim() || 'node';
  const used = new Set(existing.map((n) => n.id));
  if (!used.has(base)) return base;
  for (let i = 2; i < 999; i++) {
    const c = `${base}_${i}`;
    if (!used.has(c)) return c;
  }
  return `${base}_${Date.now()}`;
}

function createKeyId(existing: { key: string }[], prefix: string) {
  const base = (prefix || 'field').trim() || 'field';
  const used = new Set(existing.map((x) => x.key));
  if (!used.has(base)) return base;
  for (let i = 2; i < 999; i++) {
    const c = `${base}_${i}`;
    if (!used.has(c)) return c;
  }
  return `${base}_${Date.now()}`;
}

type ChatbotFlow = {
  id: number;
  tenant_id: number;
  domain: string;
  name: string;
  is_published: boolean;
  is_archived: boolean;
  published_version: number;
  published_at?: string | null;
  archived_at?: string | null;
  updated_at?: string | null;
  flow_definition?: ChatbotFlowDefinitionV1;
};

export default function ChatbotFlowsAdmin() {
  const [flows, setFlows] = useState<ChatbotFlow[]>([]);
  const [published, setPublished] = useState<ChatbotFlow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Partial<ChatbotFlow> | null>(null);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [currentDomain, setCurrentDomain] = useState<string>('real_estate');
  const [editorMode, setEditorMode] = useState<FlowEditorMode>('guided');
  const [editingLoading, setEditingLoading] = useState(false);

  const [definition, setDefinition] = useState<ChatbotFlowDefinitionV1>(defaultDefinition());
  const [definitionJson, setDefinitionJson] = useState<string>(JSON.stringify(defaultDefinition(), null, 2));
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const [previewInput, setPreviewInput] = useState('oi');
  const [previewStateJson, setPreviewStateJson] = useState('{}');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewOut, setPreviewOut] = useState<{ message: string; state: Record<string, unknown> } | null>(null);

  const [uiTenantId, setUiTenantId] = useState<string | null>(null);
  const [isSuperMode, setIsSuperMode] = useState(false);

  const nodeIds = useMemo(() => new Set((definition.nodes || []).map((n) => n.id)), [definition]);

  const leadSummaryFields = useMemo(() => {
    const raw = definition.lead_summary?.fields || [];
    return Array.isArray(raw) ? raw : [];
  }, [definition.lead_summary]);

  const leadKanbanStages = useMemo(() => {
    const raw = definition.lead_kanban?.stages || [];
    return Array.isArray(raw) ? raw : [];
  }, [definition.lead_kanban]);

  const leadSummarySourceSuggestions = useMemo(() => {
    const raw = definition.lead_summary?.source_options || [];
    if (Array.isArray(raw) && raw.length > 0) return raw;
    return [
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
    ];
  }, [definition.lead_summary?.source_options]);

  const leadSummarySourceOptions = useMemo(() => {
    const raw = definition.lead_summary?.source_options || [];
    return Array.isArray(raw) ? raw : [];
  }, [definition.lead_summary?.source_options]);

  function updateLeadSummarySourceOption(idx: number, patch: Partial<LeadSummarySourceOptionV1>) {
    setDefinition((prev) => {
      const fields = Array.isArray(prev.lead_summary?.fields) ? [...prev.lead_summary!.fields] : [];
      const opts = Array.isArray(prev.lead_summary?.source_options) ? [...prev.lead_summary!.source_options!] : [];
      const cur = opts[idx];
      if (!cur) return prev;
      opts[idx] = { ...cur, ...patch };
      return { ...prev, lead_summary: { fields, source_options: opts } };
    });
  }

  function addLeadSummarySourceOption() {
    setDefinition((prev) => {
      const fields = Array.isArray(prev.lead_summary?.fields) ? [...prev.lead_summary!.fields] : [];
      const opts = Array.isArray(prev.lead_summary?.source_options) ? [...prev.lead_summary!.source_options!] : [];
      opts.push({ value: 'custom', label: 'Personalizado (custom)' });
      return { ...prev, lead_summary: { fields, source_options: opts } };
    });
  }

  function removeLeadSummarySourceOption(idx: number) {
    setDefinition((prev) => {
      const fields = Array.isArray(prev.lead_summary?.fields) ? [...prev.lead_summary!.fields] : [];
      const opts = Array.isArray(prev.lead_summary?.source_options) ? [...prev.lead_summary!.source_options!] : [];
      opts.splice(idx, 1);
      return { ...prev, lead_summary: { fields, source_options: opts } };
    });
  }

  function moveLeadSummarySourceOption(idx: number, dir: -1 | 1) {
    setDefinition((prev) => {
      const fields = Array.isArray(prev.lead_summary?.fields) ? [...prev.lead_summary!.fields] : [];
      const opts = Array.isArray(prev.lead_summary?.source_options) ? [...prev.lead_summary!.source_options!] : [];
      const next = idx + dir;
      if (idx < 0 || idx >= opts.length) return prev;
      if (next < 0 || next >= opts.length) return prev;
      const tmp = opts[idx];
      opts[idx] = opts[next]!;
      opts[next] = tmp!;
      return { ...prev, lead_summary: { fields, source_options: opts } };
    });
  }

  function updateLeadSummaryField(idx: number, patch: Partial<LeadSummaryFieldV1>) {
    setDefinition((prev) => {
      const fields = Array.isArray(prev.lead_summary?.fields) ? [...prev.lead_summary!.fields] : [];
      const source_options = Array.isArray(prev.lead_summary?.source_options) ? [...prev.lead_summary!.source_options!] : undefined;
      const cur = fields[idx];
      if (!cur) return prev;
      fields[idx] = { ...cur, ...patch };
      return { ...prev, lead_summary: { fields, source_options } };
    });
  }

  function addLeadSummaryField() {
    setDefinition((prev) => {
      const fields = Array.isArray(prev.lead_summary?.fields) ? [...prev.lead_summary!.fields] : [];
      const source_options = Array.isArray(prev.lead_summary?.source_options) ? [...prev.lead_summary!.source_options!] : undefined;
      const key = createKeyId(fields, 'field');
      fields.push({ key, label: 'Novo campo', source: 'stage', empty_value: null });
      return { ...prev, lead_summary: { fields, source_options } };
    });
  }

  function removeLeadSummaryField(idx: number) {
    setDefinition((prev) => {
      const fields = Array.isArray(prev.lead_summary?.fields) ? [...prev.lead_summary!.fields] : [];
      const source_options = Array.isArray(prev.lead_summary?.source_options) ? [...prev.lead_summary!.source_options!] : undefined;
      fields.splice(idx, 1);
      return { ...prev, lead_summary: { fields, source_options } };
    });
  }

  function moveLeadSummaryField(idx: number, dir: -1 | 1) {
    setDefinition((prev) => {
      const fields = Array.isArray(prev.lead_summary?.fields) ? [...prev.lead_summary!.fields] : [];
      const source_options = Array.isArray(prev.lead_summary?.source_options) ? [...prev.lead_summary!.source_options!] : undefined;
      const next = idx + dir;
      if (idx < 0 || idx >= fields.length) return prev;
      if (next < 0 || next >= fields.length) return prev;
      const tmp = fields[idx];
      fields[idx] = fields[next]!;
      fields[next] = tmp!;
      return { ...prev, lead_summary: { fields, source_options } };
    });
  }

  function updateLeadKanbanStage(idx: number, patch: Partial<LeadKanbanStageV1>) {
    setDefinition((prev) => {
      const stages = Array.isArray(prev.lead_kanban?.stages) ? [...prev.lead_kanban!.stages] : [];
      const cur = stages[idx];
      if (!cur) return prev;
      stages[idx] = { ...cur, ...patch };
      return { ...prev, lead_kanban: { stages } };
    });
  }

  function addLeadKanbanStage() {
    setDefinition((prev) => {
      const stages = Array.isArray(prev.lead_kanban?.stages) ? [...prev.lead_kanban!.stages] : [];
      const used = new Set(stages.map((s) => s.id));
      const candidates = (prev.nodes || []).map((n) => n.id).filter((id) => !used.has(id));
      const id = candidates[0] || 'start';
      stages.push({ id, label: id });
      return { ...prev, lead_kanban: { stages } };
    });
  }

  function removeLeadKanbanStage(idx: number) {
    setDefinition((prev) => {
      const stages = Array.isArray(prev.lead_kanban?.stages) ? [...prev.lead_kanban!.stages] : [];
      stages.splice(idx, 1);
      return { ...prev, lead_kanban: { stages } };
    });
  }

  function moveLeadKanbanStage(idx: number, dir: -1 | 1) {
    setDefinition((prev) => {
      const stages = Array.isArray(prev.lead_kanban?.stages) ? [...prev.lead_kanban!.stages] : [];
      const next = idx + dir;
      if (idx < 0 || idx >= stages.length) return prev;
      if (next < 0 || next >= stages.length) return prev;
      const tmp = stages[idx];
      stages[idx] = stages[next]!;
      stages[next] = tmp!;
      return { ...prev, lead_kanban: { stages } };
    });
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      // Primeiro, busca o domínio atual do tenant
      const domainRes = await apiFetch('/admin/chatbot-domain');
      if (!domainRes.ok) throw new Error(`Domain: HTTP ${domainRes.status}`);
      const domainData = await domainRes.json();
      const domain = domainData.domain || 'real_estate';
      setCurrentDomain(domain);

      // Depois, busca os flows e o publicado para o domínio encontrado
      const [flowsRes, publishedRes] = await Promise.all([
        apiFetch(`/admin/chatbot-flows?domain=${domain}&include_archived=true`),
        apiFetch(`/admin/chatbot-flows/published?domain=${domain}`),
      ]);
      if (!flowsRes.ok) throw new Error(`Flows: HTTP ${flowsRes.status}`);
      if (!publishedRes.ok) throw new Error(`Published: HTTP ${publishedRes.status}`);
      const flowsData = await flowsRes.json();
      const publishedData = await publishedRes.json();
      setFlows(flowsData);
      setPublished(publishedData.flow || null);
    } catch (e) {
      setError((e as Error).message || 'Erro ao carregar flows');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    try {
      setUiTenantId(localStorage.getItem('ui_tenant_id'))
    } catch {
      setUiTenantId(null)
    }
    try {
      setIsSuperMode(!!localStorage.getItem('ui_super_admin_key'))
    } catch {
      setIsSuperMode(false)
    }
  }, [loading]);

  useEffect(() => {
    // Mantém o JSON em sync quando o editor guiado altera o objeto
    if (editorMode !== 'guided') return;
    setDefinitionJson(JSON.stringify(definition, null, 2));
  }, [definition, editorMode]);

  async function openNewFlow() {
    const def = defaultDefinition();
    setEditorMode('guided');
    setJsonError(null);
    setValidationErrors([]);
    setPreviewOut(null);
    setDefinition(def);
    setDefinitionJson(JSON.stringify(def, null, 2));
    setEditing({ name: 'Novo Flow', domain: currentDomain, flow_definition: def });
  }

  async function openEditFlow(flowId: number) {
    setEditingLoading(true);
    setError(null);
    setJsonError(null);
    setValidationErrors([]);
    setPreviewOut(null);
    try {
      const res = await apiFetch(`/admin/chatbot-flows/by-id/${flowId}`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail);
      }
      const flow = (await res.json()) as ChatbotFlow;
      const def = normalizeDefinition((flow.flow_definition || defaultDefinition()) as ChatbotFlowDefinitionV1);
      setEditorMode('guided');
      setDefinition(def);
      setDefinitionJson(JSON.stringify(def, null, 2));
      setEditing({ ...flow, flow_definition: def });
      setValidationErrors(validateDefinition(def));
    } catch (e) {
      setError((e as Error).message || 'Erro ao abrir flow');
    } finally {
      setEditingLoading(false);
    }
  }

  async function createFromTemplate() {
    setError(null);
    const template = (window.prompt('Template (ex: default)', 'default') || '').trim() || 'default';
    const name = (window.prompt('Nome do novo flow', `template_${template}`) || '').trim();
    if (!name) return;

    const overwrite = window.confirm('Se já existir um flow com esse nome, deseja sobrescrever?');
    const publish = window.confirm('Publicar automaticamente após criar?');

    try {
      const res = await apiFetch('/admin/chatbot-flows/create-from-template', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: currentDomain, template, name, overwrite, publish }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const js = (await res.json()) as { flow_id: number };
      await load();
      if (js.flow_id) {
        await openEditFlow(js.flow_id);
      }
    } catch (e) {
      setError((e as Error).message || 'Erro ao criar flow a partir de template');
    }
  }

  async function cloneFlow(flowId: number) {
    setError(null);
    const name = (window.prompt('Nome do flow clonado', `clone_${flowId}`) || '').trim();
    if (!name) return;

    const overwrite = window.confirm('Se já existir um flow com esse nome, deseja sobrescrever?');
    const publish = window.confirm('Publicar automaticamente após clonar?');

    try {
      const res = await apiFetch(`/admin/chatbot-flows/${flowId}/clone`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, overwrite, publish }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const js = (await res.json()) as { new_flow_id: number };
      await load();
      if (js.new_flow_id) {
        await openEditFlow(js.new_flow_id);
      }
    } catch (e) {
      setError((e as Error).message || 'Erro ao clonar flow');
    }
  }

  async function setArchived(flowId: number, archived: boolean) {
    setError(null);
    const action = archived ? 'arquivar' : 'desarquivar';
    if (!window.confirm(`Confirma ${action} este flow?`)) return;
    try {
      const res = await apiFetch(`/admin/chatbot-flows/${flowId}/${archived ? 'archive' : 'unarchive'}`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      await load();
    } catch (e) {
      setError((e as Error).message || `Erro ao ${action} flow`);
    }
  }

  async function publishByVersion() {
    setError(null);
    const raw = (window.prompt('Publicar qual versão? (published_version)', '') || '').trim();
    if (!raw) return;
    const v = Number(raw);
    if (!Number.isFinite(v) || v <= 0) {
      setError('Versão inválida');
      return;
    }
    if (!window.confirm(`Publicar versão ${v}?`)) return;
    try {
      const res = await apiFetch('/admin/chatbot-flows/publish-by-version', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain: currentDomain, published_version: v }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      await load();
    } catch (e) {
      setError((e as Error).message || 'Erro ao publicar por versão');
    }
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setError(null);
    setJsonError(null);

    let nextDefinition: ChatbotFlowDefinitionV1;
    if (editorMode === 'json') {
      const parsed = safeJsonParse<ChatbotFlowDefinitionV1>(definitionJson);
      if (!parsed.ok) {
        setJsonError(parsed.error);
        return;
      }
      nextDefinition = normalizeDefinition(parsed.value);
    } else {
      nextDefinition = normalizeDefinition(definition);
    }

    const errors = validateDefinition(nextDefinition);
    setValidationErrors(errors);
    if (errors.length > 0) {
      setError('Corrija os erros de validação antes de salvar.');
      return;
    }

    try {
      const payload = {
        name: editing.name || 'Novo Flow',
        domain: editing.domain || currentDomain,
        flow_definition: nextDefinition,
      };
      const res = await apiFetch('/admin/chatbot-flows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail);
      }
      setEditing(null);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onPublish(flowId: number) {
    if (!window.confirm('Publicar este flow? O flow publicado anteriormente será desativado.')) return;
    try {
      const res = await apiFetch(`/admin/chatbot-flows/${flowId}/publish`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onPreview() {
    const flowId = editing?.id;
    if (!flowId) return;

    setPreviewLoading(true);
    setError(null);

    const parsedState = safeJsonParse<Record<string, unknown>>(previewStateJson);
    if (!parsedState.ok) {
      setError(parsedState.error);
      setPreviewLoading(false);
      return;
    }

    try {
      const res = await apiFetch(`/admin/chatbot-flows/${flowId}/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: previewInput, state: parsedState.value }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const js = (await res.json()) as { message: string; state: Record<string, unknown> };
      setPreviewOut(js);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewLoading(false);
    }
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-800">Chatbot Flows</h1>
        <p className="text-sm text-slate-500">Gestão de flows de conversa por tenant</p>
        {isSuperMode && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="badge badge-neutral">Super Admin</span>
            <span className="text-slate-600">Tenant selecionado:</span>
            <span className="font-mono">{uiTenantId || '(nenhum)'}</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                window.location.href = '/super/tenants'
              }}
            >
              Trocar tenant
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                try {
                  localStorage.removeItem('ui_tenant_id')
                  setUiTenantId(null)
                } catch {
                  // ignore
                }
              }}
            >
              Limpar tenant
            </button>
          </div>
        )}
      </header>

      {loading && <p>Carregando...</p>}
      {error && <p className="text-red-600 bg-red-100 p-3 rounded-lg">{error}</p>}

      {editing && (
        <div className="card space-y-4">
          <h2 className="font-bold text-lg">{editing.id ? 'Editando' : 'Novo'} Flow</h2>
          <form onSubmit={onSave} className="space-y-4">
            <div>
              <label htmlFor="flow_name" className="block text-sm font-medium text-slate-700 mb-1">Nome do Flow</label>
              <input
                id="flow_name"
                type="text"
                value={editing.name || ''}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                className="input w-full"
                placeholder="Ex: Boas-vindas Carros"
                required
              />
            </div>

            {editingLoading && <p className="text-sm text-slate-500">Carregando definição...</p>}

            <div className="flex items-center gap-2">
              <button
                type="button"
                className={`btn btn-sm ${editorMode === 'guided' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => {
                  setEditorMode('guided');
                  const parsed = safeJsonParse<ChatbotFlowDefinitionV1>(definitionJson);
                  if (parsed.ok) setDefinition(normalizeDefinition(parsed.value));
                }}
                disabled={editingLoading}
              >
                Editor guiado
              </button>
              <button
                type="button"
                className={`btn btn-sm ${editorMode === 'json' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => {
                  setEditorMode('json');
                  setDefinitionJson(JSON.stringify(definition, null, 2));
                }}
                disabled={editingLoading}
              >
                JSON
              </button>
            </div>

            {editorMode === 'guided' ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Start node</label>
                    <select
                      className="select w-full"
                      value={definition.start}
                      onChange={(e) => setDefinition((prev) => ({ ...prev, start: e.target.value }))}
                      disabled={editingLoading}
                    >
                      {(definition.nodes || []).map((n) => (
                        <option key={n.id} value={n.id}>{n.id}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-end justify-end">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        const id = createNodeId(definition.nodes || [], 'node');
                        setDefinition((prev) => ({
                          ...prev,
                          nodes: [...(prev.nodes || []), { id, type: 'static_message', prompt: '', transitions: [] }],
                        }));
                      }}
                      disabled={editingLoading}
                    >
                      + Nó
                    </button>
                  </div>
                </div>

                <div className="space-y-3">
                  {(definition.nodes || []).map((n, nodeIdx) => (
                    <div key={n.id} className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-mono text-xs text-slate-600">{n.id}</div>
                        <button
                          type="button"
                          className="btn btn-sm btn-secondary"
                          onClick={() => {
                            setDefinition((prev) => {
                              const nodes = (prev.nodes || []).filter((x) => x.id !== n.id);
                              const start = prev.start === n.id ? (nodes[0]?.id || 'start') : prev.start;
                              const cleaned = nodes.map((x) => ({
                                ...x,
                                transitions: (x.transitions || []).filter((t) => t.to !== n.id),
                              }));
                              return { ...prev, start, nodes: cleaned };
                            });
                          }}
                          disabled={editingLoading || n.id === definition.start}
                        >
                          Remover
                        </button>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-xs font-semibold text-slate-600">ID</label>
                          <input
                            className="input"
                            value={n.id}
                            onChange={(e) => {
                              const nextId = e.target.value.trim();
                              if (!nextId) return;
                              if (nextId !== n.id && nodeIds.has(nextId)) return;
                              setDefinition((prev) => {
                                const nodes = (prev.nodes || []).map((x) => {
                                  if (x.id !== n.id) {
                                    return {
                                      ...x,
                                      transitions: (x.transitions || []).map((t) => (t.to === n.id ? { ...t, to: nextId } : t)),
                                    };
                                  }
                                  return { ...x, id: nextId };
                                });
                                const start = prev.start === n.id ? nextId : prev.start;
                                return { ...prev, start, nodes };
                              });
                            }}
                            disabled={editingLoading}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-600">Tipo</label>
                          <select
                            className="select w-full"
                            value={(FLOW_NODE_TYPES.includes(n.type as FlowNodeType) ? (n.type as FlowNodeType) : 'static_message')}
                            onChange={(e) => {
                              const v = e.target.value;
                              setDefinition((prev) => ({
                                ...prev,
                                nodes: (prev.nodes || []).map((x, i) => (i === nodeIdx ? { ...x, type: v } : x)),
                              }));
                            }}
                            disabled={editingLoading}
                          >
                            {FLOW_NODE_TYPES.map((t) => (
                              <option key={t} value={t}>{t}</option>
                            ))}
                            {!FLOW_NODE_TYPES.includes(n.type as FlowNodeType) && (
                              <option value={n.type}>custom: {n.type}</option>
                            )}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-600">Handler</label>
                          <input
                            className="input"
                            value={n.handler || ''}
                            onChange={(e) => {
                              const v = e.target.value;
                              setDefinition((prev) => ({
                                ...prev,
                                nodes: (prev.nodes || []).map((x, i) => (i === nodeIdx ? { ...x, handler: v || undefined } : x)),
                              }));
                            }}
                            disabled={editingLoading}
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-600">Prompt</label>
                        <textarea
                          className="input w-full"
                          value={n.prompt || ''}
                          onChange={(e) => {
                            const v = e.target.value;
                            setDefinition((prev) => ({
                              ...prev,
                              nodes: (prev.nodes || []).map((x, i) => (i === nodeIdx ? { ...x, prompt: v || undefined } : x)),
                            }));
                          }}
                          disabled={editingLoading}
                        />
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold text-slate-700">Transições</div>
                          <button
                            type="button"
                            className="btn btn-sm btn-secondary"
                            onClick={() => {
                              const to = definition.nodes?.[0]?.id || definition.start;
                              setDefinition((prev) => ({
                                ...prev,
                                nodes: (prev.nodes || []).map((x, i) => (i === nodeIdx ? { ...x, transitions: [...(x.transitions || []), { to }] } : x)),
                              }));
                            }}
                            disabled={editingLoading || (definition.nodes || []).length === 0}
                          >
                            + Transição
                          </button>
                        </div>

                        {(n.transitions || []).map((t, tIdx) => (
                          <div key={`${n.id}:${tIdx}`} className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end bg-white border border-slate-200 rounded-lg p-2">
                            <div className="md:col-span-2">
                              <label className="block text-xs font-semibold text-slate-600">To</label>
                              <select
                                className="select w-full"
                                value={t.to}
                                onChange={(e) => {
                                  const v = e.target.value;
                                  setDefinition((prev) => ({
                                    ...prev,
                                    nodes: (prev.nodes || []).map((x, i) => {
                                      if (i !== nodeIdx) return x;
                                      const nextTransitions = (x.transitions || []).map((tt, j) => (j === tIdx ? { ...tt, to: v } : tt));
                                      return { ...x, transitions: nextTransitions };
                                    }),
                                  }));
                                }}
                                disabled={editingLoading}
                              >
                                {(definition.nodes || []).map((nn) => (
                                  <option key={nn.id} value={nn.id}>{nn.id}</option>
                                ))}
                              </select>
                            </div>
                            <div className="md:col-span-3">
                              <label className="block text-xs font-semibold text-slate-600">When (JSON)</label>
                              <input
                                className="input w-full font-mono text-xs"
                                value={t.when ? JSON.stringify(t.when) : ''}
                                onChange={(e) => {
                                  const raw = e.target.value;
                                  if (!raw.trim()) {
                                    setDefinition((prev) => ({
                                      ...prev,
                                      nodes: (prev.nodes || []).map((x, i) => {
                                        if (i !== nodeIdx) return x;
                                        const nextTransitions = (x.transitions || []).map((tt, j) => (j === tIdx ? { ...tt, when: undefined } : tt));
                                        return { ...x, transitions: nextTransitions };
                                      }),
                                    }));
                                    return;
                                  }
                                  const parsed = safeJsonParse<Record<string, unknown>>(raw);
                                  if (!parsed.ok) return;
                                  setDefinition((prev) => ({
                                    ...prev,
                                    nodes: (prev.nodes || []).map((x, i) => {
                                      if (i !== nodeIdx) return x;
                                      const nextTransitions = (x.transitions || []).map((tt, j) => (j === tIdx ? { ...tt, when: parsed.value } : tt));
                                      return { ...x, transitions: nextTransitions };
                                    }),
                                  }));
                                }}
                                placeholder='{"eq": ["state.foo", "bar"]}'
                                disabled={editingLoading}
                              />
                            </div>
                            <div className="md:col-span-1 flex items-center justify-end">
                              <button
                                type="button"
                                className="btn btn-sm btn-secondary"
                                onClick={() => {
                                  setDefinition((prev) => ({
                                    ...prev,
                                    nodes: (prev.nodes || []).map((x, i) => {
                                      if (i !== nodeIdx) return x;
                                      const nextTransitions = (x.transitions || []).filter((_, j) => j !== tIdx);
                                      return { ...x, transitions: nextTransitions };
                                    }),
                                  }));
                                }}
                                disabled={editingLoading}
                              >
                                Remover
                              </button>
                            </div>
                            {t.to && !nodeIds.has(t.to) && (
                              <div className="md:col-span-6 text-xs text-red-600">Destino inexistente: {t.to}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="border-t border-slate-200 pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-700">Resumo do Lead</div>
                      <div className="text-xs text-slate-500">Define quais campos do state (preferences) aparecem no card/modal de Lead.</div>
                    </div>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => addLeadSummaryField()} disabled={editingLoading}>
                      + Campo
                    </button>
                  </div>

                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-xs font-semibold text-slate-700">Opções do dropdown (Fonte / source)</div>
                        <div className="text-xs text-slate-500">Você pode adicionar, remover e ordenar as opções exibidas no select.</div>
                      </div>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => addLeadSummarySourceOption()} disabled={editingLoading}>
                        + Opção
                      </button>
                    </div>

                    {leadSummarySourceOptions.length === 0 ? (
                      <div className="text-sm text-slate-500">Nenhuma opção customizada. O sistema usa as sugestões padrão.</div>
                    ) : (
                      <div className="space-y-2">
                        {leadSummarySourceOptions.map((o, idx) => (
                          <div key={`${o.value}-${idx}`} className="bg-white border border-slate-200 rounded-lg p-3">
                            <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                              <div className="md:col-span-5">
                                <label className="block text-xs font-semibold text-slate-600">Value</label>
                                <input
                                  className="input font-mono text-xs"
                                  value={o.value}
                                  onChange={(e) => updateLeadSummarySourceOption(idx, { value: e.target.value })}
                                  disabled={editingLoading}
                                  placeholder="ex: city"
                                />
                              </div>
                              <div className="md:col-span-7">
                                <label className="block text-xs font-semibold text-slate-600">Label</label>
                                <input
                                  className="input"
                                  value={o.label}
                                  onChange={(e) => updateLeadSummarySourceOption(idx, { label: e.target.value })}
                                  disabled={editingLoading}
                                  placeholder="ex: Cidade"
                                />
                              </div>
                            </div>

                            <div className="flex items-center justify-end gap-2 mt-2">
                              <button type="button" className="btn btn-secondary btn-sm" onClick={() => moveLeadSummarySourceOption(idx, -1)} disabled={editingLoading || idx === 0}>↑</button>
                              <button type="button" className="btn btn-secondary btn-sm" onClick={() => moveLeadSummarySourceOption(idx, 1)} disabled={editingLoading || idx === leadSummarySourceOptions.length - 1}>↓</button>
                              <button type="button" className="btn btn-secondary btn-sm" onClick={() => removeLeadSummarySourceOption(idx)} disabled={editingLoading}>Remover</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {leadSummaryFields.length === 0 ? (
                    <div className="text-sm text-slate-500">Nenhum campo configurado.</div>
                  ) : (
                    <div className="space-y-2">
                      {leadSummaryFields.map((f, idx) => (
                        <div key={f.key || idx} className="bg-white border border-slate-200 rounded-lg p-3">
                          <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                            <div className="md:col-span-2">
                              <label className="block text-xs font-semibold text-slate-600">Key</label>
                              <input
                                className="input"
                                value={f.key}
                                onChange={(e) => updateLeadSummaryField(idx, { key: e.target.value })}
                                disabled={editingLoading}
                              />
                            </div>
                            <div className="md:col-span-3">
                              <label className="block text-xs font-semibold text-slate-600">Label</label>
                              <input
                                className="input"
                                value={f.label}
                                onChange={(e) => updateLeadSummaryField(idx, { label: e.target.value })}
                                disabled={editingLoading}
                              />
                            </div>
                            <div className="md:col-span-4">
                              <label className="block text-xs font-semibold text-slate-600">Fonte (source)</label>
                              <div className="grid grid-cols-1 gap-2">
                                <select
                                  className="select w-full"
                                  value={
                                    leadSummarySourceSuggestions.some((x) => x.value === f.source)
                                      ? f.source
                                      : '__custom__'
                                  }
                                  onChange={(e) => {
                                    const v = e.target.value;
                                    if (v === '__custom__') return;
                                    updateLeadSummaryField(idx, { source: v });
                                  }}
                                  disabled={editingLoading}
                                >
                                  {leadSummarySourceSuggestions.map((x) => (
                                    <option key={x.value} value={x.value}>{x.label}</option>
                                  ))}
                                  <option value="__custom__">Personalizado…</option>
                                </select>

                                {(!f.source || !leadSummarySourceSuggestions.some((x) => x.value === f.source)) && (
                                  <input
                                    className="input font-mono text-xs"
                                    value={f.source}
                                    onChange={(e) => updateLeadSummaryField(idx, { source: e.target.value })}
                                    disabled={editingLoading}
                                    placeholder="Digite a fonte (ex: stage, city, price_max)"
                                  />
                                )}
                              </div>
                            </div>
                            <div className="md:col-span-3">
                              <label className="block text-xs font-semibold text-slate-600">Empty value</label>
                              <input
                                className="input"
                                value={(f.empty_value ?? '') as string}
                                onChange={(e) => updateLeadSummaryField(idx, { empty_value: e.target.value || null })}
                                disabled={editingLoading}
                                placeholder="Ex: -"
                              />
                            </div>
                          </div>

                          <div className="flex items-center justify-end gap-2 mt-2">
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => moveLeadSummaryField(idx, -1)} disabled={editingLoading || idx === 0}>↑</button>
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => moveLeadSummaryField(idx, 1)} disabled={editingLoading || idx === leadSummaryFields.length - 1}>↓</button>
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => removeLeadSummaryField(idx)} disabled={editingLoading}>Remover</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="border-t border-slate-200 pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-700">Kanban por Etapa (Flow)</div>
                      <div className="text-xs text-slate-500">Define a ordem e os nomes das colunas quando você agrupa Leads por Etapa.</div>
                    </div>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => addLeadKanbanStage()} disabled={editingLoading}>
                      + Etapa
                    </button>
                  </div>

                  {leadKanbanStages.length === 0 ? (
                    <div className="text-sm text-slate-500">Nenhuma etapa configurada.</div>
                  ) : (
                    <div className="space-y-2">
                      {leadKanbanStages.map((s, idx) => (
                        <div key={`${s.id}-${idx}`} className="bg-white border border-slate-200 rounded-lg p-3">
                          <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                            <div className="md:col-span-5">
                              <label className="block text-xs font-semibold text-slate-600">Etapa (id do node)</label>
                              <select
                                className="select w-full"
                                value={s.id}
                                onChange={(e) => updateLeadKanbanStage(idx, { id: e.target.value })}
                                disabled={editingLoading}
                              >
                                {(definition.nodes || []).map((n) => (
                                  <option key={n.id} value={n.id}>{n.id}</option>
                                ))}
                              </select>
                            </div>
                            <div className="md:col-span-7">
                              <label className="block text-xs font-semibold text-slate-600">Label</label>
                              <input
                                className="input"
                                value={s.label}
                                onChange={(e) => updateLeadKanbanStage(idx, { label: e.target.value })}
                                disabled={editingLoading}
                              />
                            </div>
                          </div>

                          <div className="flex items-center justify-end gap-2 mt-2">
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => moveLeadKanbanStage(idx, -1)} disabled={editingLoading || idx === 0}>↑</button>
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => moveLeadKanbanStage(idx, 1)} disabled={editingLoading || idx === leadKanbanStages.length - 1}>↓</button>
                            <button type="button" className="btn btn-secondary btn-sm" onClick={() => removeLeadKanbanStage(idx)} disabled={editingLoading}>Remover</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div>
                <label htmlFor="flow_definition" className="block text-sm font-medium text-slate-700 mb-1">Definição (JSON)</label>
                <textarea
                  id="flow_definition"
                  name="flow_definition"
                  className="input font-mono w-full h-96 text-xs"
                  value={definitionJson}
                  onChange={(e) => setDefinitionJson(e.target.value)}
                  disabled={editingLoading}
                />
              </div>
            )}

            {validationErrors.length > 0 && (
              <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 space-y-1">
                {validationErrors.map((msg, idx) => (
                  <div key={idx}>{msg}</div>
                ))}
              </div>
            )}

            <div className="border-t border-slate-200 pt-4 space-y-2">
              <div className="text-sm font-semibold text-slate-700">Preview</div>
              {!editing.id ? (
                <div className="text-sm text-slate-500">Salve o flow primeiro para habilitar o preview.</div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-600">Input</label>
                      <input className="input" value={previewInput} onChange={(e) => setPreviewInput(e.target.value)} disabled={previewLoading || editingLoading} />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-600">State (JSON)</label>
                      <input className="input font-mono text-xs" value={previewStateJson} onChange={(e) => setPreviewStateJson(e.target.value)} disabled={previewLoading || editingLoading} />
                    </div>
                  </div>
                  <div>
                    <button type="button" className="btn btn-secondary" onClick={() => void onPreview()} disabled={previewLoading || editingLoading}>
                      {previewLoading ? 'Executando...' : 'Executar preview'}
                    </button>
                    <div className="text-xs text-slate-500 mt-2">Obs: preview usa a definição salva no backend. Salve para refletir alterações.</div>
                  </div>
                  {previewOut && (
                    <div className="text-sm bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
                      <div><span className="font-semibold">Mensagem:</span> {previewOut.message}</div>
                      <div>
                        <div className="font-semibold">State:</div>
                        <pre className="text-xs bg-white border border-slate-200 rounded p-2 overflow-auto">{JSON.stringify(previewOut.state, null, 2)}</pre>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {jsonError && <p className="text-red-600 text-sm">{jsonError}</p>}
            <div className="flex items-center gap-4">
              <button type="submit" className="btn btn-primary" disabled={editingLoading || validationErrors.length > 0}>Salvar</button>
              <button type="button" onClick={() => setEditing(null)} className="btn btn-secondary">Cancelar</button>
            </div>
          </form>
        </div>
      )}

      {!editing && (
        <div className="card space-y-4">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="font-bold">Flow Publicado</h2>
              {published ? (
                <p className="text-sm text-slate-600">{published.name} (v{published.published_version})</p>
              ) : (
                <p className="text-sm text-slate-500">Nenhum flow publicado.</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => void publishByVersion()} className="btn btn-secondary">Publicar por versão</button>
              <button onClick={() => void createFromTemplate()} className="btn btn-secondary">Criar do template</button>
              <button onClick={() => void openNewFlow()} className="btn btn-primary">Novo Flow</button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="table min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-600">
                  <th>Nome</th>
                  <th>Status</th>
                  <th>Versão</th>
                  <th>Atualizado em</th>
                  <th>Arquivado em</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {flows.map(flow => (
                  <tr key={flow.id} className="table-row">
                    <td>{flow.name}</td>
                    <td>
                      {flow.is_archived ? (
                        <span className='badge badge-neutral'>Arquivado</span>
                      ) : flow.is_published ? (
                        <span className='badge badge-success'>Publicado</span>
                      ) : (
                        <span className='badge badge-neutral'>Draft</span>
                      )}
                    </td>
                    <td>{flow.published_version || '-'}</td>
                    <td>{flow.updated_at ? new Date(flow.updated_at).toLocaleString() : '-'}</td>
                    <td>{flow.archived_at ? new Date(flow.archived_at).toLocaleString() : '-'}</td>
                    <td className="flex gap-2">
                      <button onClick={() => void openEditFlow(flow.id)} className="btn btn-sm btn-secondary">Editar</button>
                      <button onClick={() => void cloneFlow(flow.id)} className="btn btn-sm btn-secondary">Clonar</button>
                      {!flow.is_archived && !flow.is_published && (
                        <button onClick={() => onPublish(flow.id)} className="btn btn-sm btn-primary">Publicar</button>
                      )}
                      {flow.is_archived ? (
                        <button onClick={() => void setArchived(flow.id, false)} className="btn btn-sm btn-secondary">Desarquivar</button>
                      ) : (
                        <button onClick={() => void setArchived(flow.id, true)} className="btn btn-sm btn-secondary">Arquivar</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
