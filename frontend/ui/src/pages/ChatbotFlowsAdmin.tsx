import React, { useEffect, useState } from 'react';
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

type ChatbotFlowDefinitionV1 = {
  version: number;
  start: string;
  nodes: FlowNodeV1[];
};

type ChatbotFlow = {
  id: number;
  tenant_id: number;
  domain: string;
  name: string;
  is_published: boolean;
  published_version: number;
  published_at?: string | null;
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

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [flowsRes, publishedRes] = await Promise.all([
        apiFetch('/admin/re/chatbot-flows'),
        apiFetch('/admin/re/chatbot-flows/published'),
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

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setError(null);
    setJsonError(null);

    let definition: ChatbotFlowDefinitionV1;
    try {
      const form = e.target as HTMLFormElement;
      const textarea = form.elements.namedItem('flow_definition') as HTMLTextAreaElement;
      definition = JSON.parse(textarea.value);
    } catch {
      setJsonError('JSON inválido');
      return;
    }

    try {
      const payload = {
        name: editing.name || 'Novo Flow',
        domain: editing.domain || 'real_estate',
        flow_definition: definition,
      };
      const res = await apiFetch('/admin/re/chatbot-flows', {
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
      const res = await apiFetch(`/admin/re/chatbot-flows/${flowId}/publish`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-800">Chatbot Flows</h1>
        <p className="text-sm text-slate-500">Gestão de flows de conversa por tenant</p>
      </header>

      {loading && <p>Carregando...</p>}
      {error && <p className="text-red-600 bg-red-100 p-3 rounded-lg">{error}</p>}

      {editing && (
        <div className="card space-y-4">
          <h2 className="font-bold text-lg">{editing.id ? 'Editando' : 'Novo'} Flow: {editing.name}</h2>
          <form onSubmit={onSave} className="space-y-4">
            <textarea
              name="flow_definition"
              className="input font-mono w-full h-96 text-xs"
              defaultValue={JSON.stringify(editing.flow_definition || { version: 1, start: 'start', nodes: [] }, null, 2)}
            />
            {jsonError && <p className="text-red-600 text-sm">{jsonError}</p>}
            <div className="flex items-center gap-4">
              <button type="submit" className="btn btn-primary">Salvar</button>
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
            <button onClick={() => setEditing({ name: 'Novo Flow', domain: 'real_estate' })} className="btn btn-primary">Novo Flow</button>
          </div>
          <div className="overflow-x-auto">
            <table className="table min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-600">
                  <th>Nome</th>
                  <th>Status</th>
                  <th>Versão</th>
                  <th>Atualizado em</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {flows.map(flow => (
                  <tr key={flow.id} className="table-row">
                    <td>{flow.name}</td>
                    <td>{flow.is_published ? <span className='badge badge-success'>Publicado</span> : <span className='badge badge-neutral'>Draft</span>}</td>
                    <td>{flow.published_version || '-'}</td>
                    <td>{flow.updated_at ? new Date(flow.updated_at).toLocaleString() : '-'}</td>
                    <td className="flex gap-2">
                      <button onClick={() => {
                        const flowToEdit = flows.find(f => f.id === flow.id);
                        if (flowToEdit) setEditing(flowToEdit);
                      }} className="btn btn-sm btn-secondary">Editar</button>
                      {!flow.is_published && (
                        <button onClick={() => onPublish(flow.id)} className="btn btn-sm btn-primary">Publicar</button>
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
