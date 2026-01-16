import React from 'react';

type ChatbotFlow = {
  id: number;
  domain: string;
  name: string;
  is_published: boolean;
  is_archived: boolean;
  published_version: number;
  published_at?: string | null;
  archived_at?: string | null;
  updated_at?: string | null;
};

type PublishedFlow = {
  domain: string;
  name: string;
  published_version: number;
};

type Props = {
  flows: ChatbotFlow[];
  published: PublishedFlow | null;
  onPublishByVersion: () => void;
  onCreateFromTemplate: () => void;
  onOpenNewFlow: () => void;
  onOpenEditFlow: (flowId: number) => void;
  onCloneFlow: (flowId: number) => void;
  onPublishFlow: (flowId: number) => void;
  onSetArchived: (flowId: number, archived: boolean) => void;
};

export function ChatbotFlowsTable({
  flows,
  published,
  onPublishByVersion,
  onCreateFromTemplate,
  onOpenNewFlow,
  onOpenEditFlow,
  onCloneFlow,
  onPublishFlow,
  onSetArchived,
}: Props) {
  return (
    <div className="card space-y-4">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="font-bold">Flow Publicado</h2>
          {published ? (
            <p className="text-sm text-slate-600">
              <span className="font-mono">{published.domain}</span> / {published.name} (v{published.published_version})
            </p>
          ) : (
            <p className="text-sm text-slate-500">Nenhum flow publicado.</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onPublishByVersion} className="btn btn-secondary">
            Publicar por versão
          </button>
          <button onClick={onCreateFromTemplate} className="btn btn-secondary">
            Criar do template
          </button>
          <button onClick={onOpenNewFlow} className="btn btn-primary">
            Novo Flow
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="table min-w-full text-sm">
          <thead>
            <tr className="text-left text-slate-600">
              <th>Domínio</th>
              <th>Nome</th>
              <th>Status</th>
              <th>Versão</th>
              <th>Atualizado em</th>
              <th>Arquivado em</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {flows.map((flow) => (
              <tr key={flow.id} className="table-row">
                <td className="font-mono text-xs">{flow.domain}</td>
                <td>{flow.name}</td>
                <td>
                  {flow.is_archived ? (
                    <span className="badge badge-neutral">Arquivado</span>
                  ) : flow.is_published ? (
                    <span className="badge badge-success">Publicado</span>
                  ) : (
                    <span className="badge badge-neutral">Draft</span>
                  )}
                </td>
                <td>{flow.published_version || '-'}</td>
                <td>{flow.updated_at ? new Date(flow.updated_at).toLocaleString() : '-'}</td>
                <td>{flow.archived_at ? new Date(flow.archived_at).toLocaleString() : '-'}</td>
                <td className="flex gap-2">
                  <button onClick={() => onOpenEditFlow(flow.id)} className="btn btn-sm btn-secondary">
                    Editar
                  </button>
                  <button onClick={() => onCloneFlow(flow.id)} className="btn btn-sm btn-secondary">
                    Clonar
                  </button>
                  {!flow.is_archived && !flow.is_published && (
                    <button onClick={() => onPublishFlow(flow.id)} className="btn btn-sm btn-primary">
                      Publicar
                    </button>
                  )}
                  {flow.is_archived ? (
                    <button onClick={() => onSetArchived(flow.id, false)} className="btn btn-sm btn-secondary">
                      Desarquivar
                    </button>
                  ) : (
                    <button onClick={() => onSetArchived(flow.id, true)} className="btn btn-sm btn-secondary">
                      Arquivar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
