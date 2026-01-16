import React, { useCallback, useEffect, useMemo, useState } from 'react';

import {
  type ChatbotFlowDefinitionV1,
  type FlowNodeV1,
  type FlowTransitionV1,
  type LeadKanbanStageV1,
  type LeadSummaryFieldV1,
  type LeadSummarySourceOptionV1,
  defaultDefinition,
  normalizeDefinition,
  validateDefinition,
  createNodeId,
  safeJsonParse,
  splitCommaList,
} from '../lib/chatbotFlowDefinitionV1';

import { FlowCommandBar } from './chatbotFlowsAdmin/FlowCommandBar';
import { FlowNodesSidebar } from './chatbotFlowsAdmin/FlowNodesSidebar';
import { FlowNodeBasicsEditor } from './chatbotFlowsAdmin/FlowNodeBasicsEditor';
import { FlowNodeConfigEditor } from './chatbotFlowsAdmin/FlowNodeConfigEditor';
import { FlowTransitionsEditor } from './chatbotFlowsAdmin/FlowTransitionsEditor';
import { FlowLeadSummaryEditor } from './chatbotFlowsAdmin/FlowLeadSummaryEditor';
import { FlowLeadKanbanEditor } from './chatbotFlowsAdmin/FlowLeadKanbanEditor';
import { FlowPreviewPanel } from './chatbotFlowsAdmin/FlowPreviewPanel';
import { ChatbotFlowsTable } from './chatbotFlowsAdmin/ChatbotFlowsTable';

import { previewFlowCommands } from '../lib/chatbotFlowEditorV1';
import { FLOW_NODE_TYPE_LABELS, FLOW_NODE_TYPES, type FlowNodeType } from '../lib/chatbotFlowNodeCatalog';
import {
  cloneFlow as apiCloneFlow,
  createFromTemplate as apiCreateFromTemplate,
  getFlowById as apiGetFlowById,
  getPublishedFlowForDomain,
  getTenantChatbotDomain,
  listFlowsForDomain,
  previewFlow as apiPreviewFlow,
  publishByVersion as apiPublishByVersion,
  publishFlow as apiPublishFlow,
  saveFlow as apiSaveFlow,
  setArchived as apiSetArchived,
} from '../lib/chatbotFlowsAdminService';
import {
  addLeadKanbanStageToDefinition,
  addLeadSummaryFieldToDefinition,
  addLeadSummarySourceOptionToDefinition,
  addTransitionToNode,
  getNodeConfig,
  moveLeadKanbanStageInDefinition,
  moveLeadSummaryFieldInDefinition,
  moveLeadSummarySourceOptionInDefinition,
  removeLeadKanbanStageFromDefinition,
  removeLeadSummaryFieldFromDefinition,
  removeLeadSummarySourceOptionFromDefinition,
  removeNodeFromDefinition,
  removeTransitionFromNode,
  renameNodeInDefinition,
  setTransitionWhenInDefinition,
  updateLeadKanbanStageInDefinition,
  updateLeadSummaryFieldInDefinition,
  updateLeadSummarySourceOptionInDefinition,
  updateNodeConfigValueInDefinition,
  updateNodeInDefinition,
  updateTransitionInDefinition,
} from '../lib/chatbotFlowMutationsV1';

type FlowEditorMode = 'guided' | 'json';

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
  const [selectedNodeId, setSelectedNodeId] = useState<string>('start');

  const [commandText, setCommandText] = useState<string>('');
  const [commandError, setCommandError] = useState<string | null>(null);
  const [commandApplied, setCommandApplied] = useState<string[]>([]);

  const commandPreview = useMemo(() => {
    const txt = (commandText || '').trim();
    if (!txt) return { previewError: null as string | null, previewLines: [] as string[] };

    const res = previewFlowCommands(definition, txt);
    if (!res.ok) return { previewError: res.error, previewLines: [] as string[] };
    return { previewError: null as string | null, previewLines: res.applied };
  }, [commandText, definition]);

  const nodeIds = useMemo(() => new Set((definition.nodes || []).map((n) => (n.id || '').trim()).filter(Boolean)), [definition]);

  const leadSummaryFields = useMemo(() => {
    const raw = definition.lead_summary?.fields || [];
    return Array.isArray(raw) ? raw : [];
  }, [definition.lead_summary]);

  const leadKanbanStages = useMemo(() => {
    const raw = definition.lead_kanban?.stages || [];
    return Array.isArray(raw) ? raw : [];
  }, [definition.lead_kanban]);

  const selectedNode = useMemo(() => (definition.nodes || []).find((n) => n.id === selectedNodeId) || null, [definition.nodes, selectedNodeId]);
  const selectedNodeIdx = useMemo(
    () => (definition.nodes || []).findIndex((n) => n.id === selectedNodeId),
    [definition.nodes, selectedNodeId],
  );

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

  function updateNodeConfigValue(nodeIdx: number, key: string, value: unknown) {
    setDefinition((prev) => updateNodeConfigValueInDefinition(prev, nodeIdx, key, value));
  }

  function updateTransition(nodeIdx: number, tIdx: number, patch: Partial<FlowTransitionV1>) {
    setDefinition((prev) => updateTransitionInDefinition(prev, nodeIdx, tIdx, patch));
  }

  function updateTransitionWhen(nodeIdx: number, tIdx: number, nextWhen: Record<string, unknown> | undefined) {
    setDefinition((prev) => setTransitionWhenInDefinition(prev, nodeIdx, tIdx, nextWhen));
  }

  function updateLeadSummarySourceOption(idx: number, patch: Partial<LeadSummarySourceOptionV1>) {
    setDefinition((prev) => updateLeadSummarySourceOptionInDefinition(prev, idx, patch));
  }

  function addLeadSummarySourceOption() {
    setDefinition((prev) => addLeadSummarySourceOptionToDefinition(prev));
  }

  function removeLeadSummarySourceOption(idx: number) {
    setDefinition((prev) => removeLeadSummarySourceOptionFromDefinition(prev, idx));
  }

  function moveLeadSummarySourceOption(idx: number, dir: -1 | 1) {
    setDefinition((prev) => moveLeadSummarySourceOptionInDefinition(prev, idx, dir));
  }

  function updateLeadSummaryField(idx: number, patch: Partial<LeadSummaryFieldV1>) {
    setDefinition((prev) => updateLeadSummaryFieldInDefinition(prev, idx, patch));
  }

  function addLeadSummaryField() {
    setDefinition((prev) => addLeadSummaryFieldToDefinition(prev));
  }

  function removeLeadSummaryField(idx: number) {
    setDefinition((prev) => removeLeadSummaryFieldFromDefinition(prev, idx));
  }

  function moveLeadSummaryField(idx: number, dir: -1 | 1) {
    setDefinition((prev) => moveLeadSummaryFieldInDefinition(prev, idx, dir));
  }

  function updateLeadKanbanStage(idx: number, patch: Partial<LeadKanbanStageV1>) {
    setDefinition((prev) => updateLeadKanbanStageInDefinition(prev, idx, patch));
  }

  function addLeadKanbanStage() {
    setDefinition((prev) => addLeadKanbanStageToDefinition(prev));
  }

  function removeLeadKanbanStage(idx: number) {
    setDefinition((prev) => removeLeadKanbanStageFromDefinition(prev, idx));
  }

  function moveLeadKanbanStage(idx: number, dir: -1 | 1) {
    setDefinition((prev) => moveLeadKanbanStageInDefinition(prev, idx, dir));
  }

  const loadForDomain = useCallback(async (domain: string) => {
    const d = (domain || '').trim() || 'real_estate'
    setLoading(true)
    setError(null)
    try {
      const [flowsData, publishedFlow] = await Promise.all([listFlowsForDomain(d), getPublishedFlowForDomain(d)])
      setFlows(flowsData as unknown as ChatbotFlow[])
      setPublished((publishedFlow as unknown as ChatbotFlow) || null)
      setCurrentDomain(d)
    } catch (e) {
      setError((e as Error).message || 'Erro ao carregar flows')
    } finally {
      setLoading(false)
    }
  }, [])

  const load = useCallback(async () => {
    try {
      // Primeiro, busca o domínio atual do tenant
      const domain = await getTenantChatbotDomain();
      await loadForDomain(domain)
    } catch (e) {
      setError((e as Error).message || 'Erro ao carregar flows')
    }
  }, [loadForDomain])

  useEffect(() => {
    load();
  }, [load]);

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

  useEffect(() => {
    // Garantir que sempre exista um nó selecionado válido
    const ids = (definition.nodes || []).map((n) => n.id);
    if (!ids.includes(selectedNodeId)) {
      setSelectedNodeId(definition.start || ids[0] || 'start');
    }
  }, [definition.nodes, definition.start, selectedNodeId]);

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
      const flow = (await apiGetFlowById(flowId)) as unknown as ChatbotFlow;
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
      const js = await apiCreateFromTemplate({ domain: currentDomain, template, name, overwrite, publish });
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
      const js = await apiCloneFlow(flowId, { name, overwrite, publish });
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
      await apiSetArchived(flowId, archived);
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
      await apiPublishByVersion({ domain: currentDomain, published_version: v });
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
      await apiSaveFlow(payload);
      setEditing(null);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onPublish(flowId: number) {
    if (!window.confirm('Publicar este flow? O flow publicado anteriormente será desativado.')) return;
    try {
      await apiPublishFlow(flowId);
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
      const js = await apiPreviewFlow(flowId, { input: previewInput, state: parsedState.value });
      setPreviewOut(js);
      try {
        setPreviewStateJson(JSON.stringify(js.state || {}, null, 0));
      } catch {
        // ignore
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewLoading(false);
    }
  }

  function onResetPreview() {
    setPreviewInput('oi');
    setPreviewStateJson('{}');
    setPreviewOut(null);
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-800">Chatbot Flows</h1>
        <p className="text-sm text-slate-500">Gestão de flows de conversa por tenant</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-600">Domínio ativo:</span>
          <span className="badge badge-neutral font-mono">{currentDomain}</span>
          <select
            className="select select-sm"
            value={currentDomain}
            onChange={(e) => {
              void loadForDomain(e.target.value)
            }}
            disabled={loading}
          >
            <option value="real_estate">real_estate</option>
            <option value="car_dealer">car_dealer</option>
          </select>
        </div>
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="flow_domain" className="block text-sm font-medium text-slate-700 mb-1">Domínio</label>
                <select
                  id="flow_domain"
                  className="select w-full font-mono"
                  value={(editing.domain || currentDomain) as string}
                  onChange={(e) => setEditing({ ...editing, domain: e.target.value })}
                  disabled={editingLoading}
                >
                  <option value="real_estate">real_estate</option>
                  <option value="car_dealer">car_dealer</option>
                </select>
                <div className="text-xs text-slate-500 mt-1">Este domínio define qual flow será usado pelo tenant.</div>
              </div>
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
                <FlowCommandBar
                  commandText={commandText}
                  onChangeCommandText={setCommandText}
                  commandError={commandError}
                  commandApplied={commandApplied}
                  nodeIdOptions={(definition.nodes || []).map((n) => n.id)}
                  previewError={commandPreview.previewError}
                  previewLines={commandPreview.previewLines}
                  disabled={editingLoading}
                  onClear={() => {
                    setCommandText('');
                    setCommandError(null);
                    setCommandApplied([]);
                  }}
                  onApply={() => {
                    setCommandError(null);
                    setCommandApplied([]);

                    const res = previewFlowCommands(definition, commandText);
                    if (!res.ok) {
                      setCommandError(res.error);
                      return;
                    }

                    setDefinition(res.definition);
                    if (res.suggestedSelectedNodeId) setSelectedNodeId(res.suggestedSelectedNodeId);
                    setCommandApplied(res.applied);
                    setCommandText('');
                  }}
                />

                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                  <FlowNodesSidebar
                    nodes={(definition.nodes || []).map((n) => ({ id: n.id, type: n.type }))}
                    selectedNodeId={selectedNodeId}
                    startNodeId={definition.start}
                    getNodeTypeLabel={(nodeType) => (FLOW_NODE_TYPE_LABELS[nodeType as FlowNodeType] || nodeType)}
                    onAddNode={() => {
                      const id = createNodeId(definition.nodes || [], 'node');
                      setDefinition((prev) => ({
                        ...prev,
                        nodes: [...(prev.nodes || []), { id, type: 'static_message', prompt: '', transitions: [] }],
                      }));
                      setSelectedNodeId(id);
                    }}
                    onSelectNode={setSelectedNodeId}
                    onChangeStartNode={(nodeId) => setDefinition((prev) => ({ ...prev, start: nodeId }))}
                    disabled={editingLoading}
                  />

                  <div className="md:col-span-3 bg-white border border-slate-200 rounded-lg p-4 space-y-3">
                    {!selectedNode ? (
                      <div className="text-sm text-slate-500">Selecione um nó para editar.</div>
                    ) : (
                      <>
                        <FlowNodeBasicsEditor
                          nodeId={selectedNode.id}
                          startNodeId={definition.start}
                          nodeType={FLOW_NODE_TYPES.includes(selectedNode.type as FlowNodeType) ? (selectedNode.type as string) : 'static_message'}
                          nodeTypeOptions={FLOW_NODE_TYPES.map((t) => ({ value: t, label: FLOW_NODE_TYPE_LABELS[t] }))}
                          showCustomNodeTypeOption={!FLOW_NODE_TYPES.includes(selectedNode.type as FlowNodeType)}
                          handler={selectedNode.handler || ''}
                          prompt={selectedNode.prompt || ''}
                          disabled={editingLoading}
                          onRemove={() => {
                            const res = removeNodeFromDefinition(definition, selectedNode.id);
                            setDefinition(res.definition);
                            setSelectedNodeId(res.nextSelectedNodeId);
                          }}
                          onChangeNodeId={(raw) => {
                            const nextId = raw.trim();
                            if (!nextId) return;
                            if (nextId !== selectedNode.id && nodeIds.has(nextId)) return;
                            const res = renameNodeInDefinition(definition, selectedNode.id, nextId);
                            setDefinition(res.definition);
                            setSelectedNodeId(res.nextSelectedNodeId);
                          }}
                          onChangeNodeType={(v) => {
                            setDefinition((prev) => updateNodeInDefinition(prev, selectedNodeIdx, { type: v }));
                          }}
                          onChangeHandler={(v) => {
                            setDefinition((prev) => updateNodeInDefinition(prev, selectedNodeIdx, { handler: v || undefined }));
                          }}
                          onChangePrompt={(v) => {
                            setDefinition((prev) => updateNodeInDefinition(prev, selectedNodeIdx, { prompt: v || undefined }));
                          }}
                        />

                        <FlowNodeConfigEditor
                          nodeType={selectedNode.type}
                          cfg={getNodeConfig(selectedNode as FlowNodeV1)}
                          advancedConfigJson={selectedNode.config ? JSON.stringify(selectedNode.config) : ''}
                          disabled={editingLoading}
                          onUpdateConfigValue={(key, value) => updateNodeConfigValue(selectedNodeIdx, key, value)}
                          onChangeAdvancedConfigRaw={(raw) => {
                            if (!raw.trim()) {
                              setDefinition((prev) => updateNodeInDefinition(prev, selectedNodeIdx, { config: undefined }));
                              return;
                            }
                            const parsed = safeJsonParse<Record<string, unknown>>(raw);
                            if (!parsed.ok) return;
                            setDefinition((prev) => updateNodeInDefinition(prev, selectedNodeIdx, { config: parsed.value }));
                          }}
                        />

                        <FlowTransitionsEditor
                          nodeId={selectedNode.id}
                          transitions={selectedNode.transitions || []}
                          nodeOptions={(definition.nodes || []).map((n) => ({ id: n.id }))}
                          disabled={editingLoading}
                          splitCommaList={splitCommaList}
                          onAddTransition={() => {
                            const to = definition.nodes?.[0]?.id || definition.start;
                            setDefinition((prev) => addTransitionToNode(prev, selectedNodeIdx, to));
                          }}
                          onRemoveTransition={(tIdx) => {
                            setDefinition((prev) => removeTransitionFromNode(prev, selectedNodeIdx, tIdx));
                          }}
                          onUpdateTransitionTo={(tIdx, to) => updateTransition(selectedNodeIdx, tIdx, { to })}
                          onUpdateTransitionWhen={(tIdx, when) => updateTransitionWhen(selectedNodeIdx, tIdx, when)}
                        />
                      </>
                    )}
                  </div>
                </div>

                <FlowLeadSummaryEditor
                  leadSummaryFields={leadSummaryFields}
                  leadSummarySourceOptions={leadSummarySourceOptions}
                  leadSummarySourceSuggestions={leadSummarySourceSuggestions}
                  disabled={editingLoading}
                  onAddField={addLeadSummaryField}
                  onUpdateField={updateLeadSummaryField}
                  onMoveField={moveLeadSummaryField}
                  onRemoveField={removeLeadSummaryField}
                  onAddSourceOption={addLeadSummarySourceOption}
                  onUpdateSourceOption={updateLeadSummarySourceOption}
                  onMoveSourceOption={moveLeadSummarySourceOption}
                  onRemoveSourceOption={removeLeadSummarySourceOption}
                />

                <FlowLeadKanbanEditor
                  stages={leadKanbanStages}
                  nodeOptions={(definition.nodes || []).map((n) => ({ id: n.id }))}
                  disabled={editingLoading}
                  onAddStage={addLeadKanbanStage}
                  onUpdateStage={updateLeadKanbanStage}
                  onMoveStage={moveLeadKanbanStage}
                  onRemoveStage={removeLeadKanbanStage}
                />
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

            <FlowPreviewPanel
              canPreview={Boolean(editing.id)}
              previewInput={previewInput}
              previewStateJson={previewStateJson}
              previewLoading={previewLoading}
              previewOut={previewOut}
              onChangePreviewInput={setPreviewInput}
              onChangePreviewStateJson={setPreviewStateJson}
              onRunPreview={() => void onPreview()}
              onResetPreview={onResetPreview}
              disabled={editingLoading}
            />

            {jsonError && <p className="text-red-600 text-sm">{jsonError}</p>}
            <div className="flex items-center gap-4">
              <button type="submit" className="btn btn-primary" disabled={editingLoading || validationErrors.length > 0}>Salvar</button>
              <button type="button" onClick={() => setEditing(null)} className="btn btn-secondary">Cancelar</button>
            </div>
          </form>
        </div>
      )}

      {!editing && (
        <ChatbotFlowsTable
          flows={flows}
          published={published ? { domain: published.domain, name: published.name, published_version: published.published_version } : null}
          onPublishByVersion={() => void publishByVersion()}
          onCreateFromTemplate={() => void createFromTemplate()}
          onOpenNewFlow={() => void openNewFlow()}
          onOpenEditFlow={(flowId) => void openEditFlow(flowId)}
          onCloneFlow={(flowId) => void cloneFlow(flowId)}
          onPublishFlow={(flowId) => onPublish(flowId)}
          onSetArchived={(flowId, archived) => void setArchived(flowId, archived)}
        />
      )}
    </section>
  );
}
