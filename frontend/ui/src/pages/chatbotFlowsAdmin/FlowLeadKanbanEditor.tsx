import React from 'react';

type Stage = {
  id: string;
  label: string;
};

type NodeOption = {
  id: string;
};

type Props = {
  stages: Stage[];
  nodeOptions: NodeOption[];
  onAddStage: () => void;
  onUpdateStage: (idx: number, patch: Partial<Stage>) => void;
  onMoveStage: (idx: number, dir: -1 | 1) => void;
  onRemoveStage: (idx: number) => void;
  disabled: boolean;
};

export function FlowLeadKanbanEditor({ stages, nodeOptions, onAddStage, onUpdateStage, onMoveStage, onRemoveStage, disabled }: Props) {
  return (
    <div className="border-t border-slate-200 pt-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-700">Kanban por Etapa (Flow)</div>
          <div className="text-xs text-slate-500">Define a ordem e os nomes das colunas quando você agrupa Leads por Etapa.</div>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onAddStage} disabled={disabled}>
          + Etapa
        </button>
      </div>

      {stages.length === 0 ? (
        <div className="text-sm text-slate-500">Nenhuma etapa configurada.</div>
      ) : (
        <div className="space-y-2">
          {stages.map((s, idx) => (
            <div key={`${s.id}-${idx}`} className="bg-white border border-slate-200 rounded-lg p-3">
              <div className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                <div className="md:col-span-5">
                  <label className="block text-xs font-semibold text-slate-600">Etapa (id do node)</label>
                  <select className="select w-full" value={s.id} onChange={(e) => onUpdateStage(idx, { id: e.target.value })} disabled={disabled}>
                    {nodeOptions.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.id}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="md:col-span-7">
                  <label className="block text-xs font-semibold text-slate-600">Label</label>
                  <input className="input" value={s.label} onChange={(e) => onUpdateStage(idx, { label: e.target.value })} disabled={disabled} />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 mt-2">
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onMoveStage(idx, -1)} disabled={disabled || idx === 0}>
                  ↑
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onMoveStage(idx, 1)} disabled={disabled || idx === stages.length - 1}>
                  ↓
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onRemoveStage(idx)} disabled={disabled}>
                  Remover
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
