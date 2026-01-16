import React from 'react';

type Transition = {
  to: string;
  when?: Record<string, unknown>;
};

type NodeOption = {
  id: string;
};

type Props = {
  nodeId: string;
  transitions: Transition[];
  nodeOptions: NodeOption[];
  disabled: boolean;
  onAddTransition: () => void;
  onRemoveTransition: (tIdx: number) => void;
  onUpdateTransitionTo: (tIdx: number, to: string) => void;
  onUpdateTransitionWhen: (tIdx: number, when: Record<string, unknown> | undefined) => void;
  splitCommaList: (raw: string) => string[];
};

export function FlowTransitionsEditor({
  nodeId,
  transitions,
  nodeOptions,
  disabled,
  onAddTransition,
  onRemoveTransition,
  onUpdateTransitionTo,
  onUpdateTransitionWhen,
  splitCommaList,
}: Props) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-700">Transições</div>
        <button type="button" className="btn btn-sm btn-secondary" onClick={onAddTransition} disabled={disabled || nodeOptions.length === 0}>
          + Transição
        </button>
      </div>

      {(transitions || []).map((t, tIdx) => (
        <div key={`${nodeId}:${tIdx}`} className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end bg-slate-50 border border-slate-200 rounded-lg p-2">
          <div className="md:col-span-2">
            <label className="block text-xs font-semibold text-slate-600">Ir para</label>
            <select className="select w-full" value={t.to} onChange={(e) => onUpdateTransitionTo(tIdx, e.target.value)} disabled={disabled}>
              {nodeOptions.map((nn) => (
                <option key={nn.id} value={nn.id}>
                  {nn.id}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs font-semibold text-slate-600">Condição</label>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <button
                type="button"
                className={`btn btn-xs ${!t.when ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => onUpdateTransitionWhen(tIdx, undefined)}
                disabled={disabled}
              >
                default
              </button>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  className={`btn btn-xs ${(() => {
                    const whenObj = (t.when || {}) as Record<string, unknown>;
                    return Array.isArray(whenObj.contains_any);
                  })()
                    ? 'btn-primary'
                    : 'btn-secondary'}`}
                  onClick={() => onUpdateTransitionWhen(tIdx, { contains_any: ['carro'] })}
                  disabled={disabled}
                >
                  contains_any
                </button>
                {(() => {
                  const whenObj = (t.when || {}) as Record<string, unknown>;
                  const arr = Array.isArray(whenObj.contains_any) ? (whenObj.contains_any as unknown[]) : null;
                  if (!arr) return null;
                  const value = arr.map((x) => String(x)).join(', ');
                  return (
                    <input
                      className="input input-sm font-mono"
                      placeholder="carro, veiculo"
                      value={value}
                      onChange={(e) => onUpdateTransitionWhen(tIdx, { contains_any: splitCommaList(e.target.value) })}
                      disabled={disabled}
                    />
                  );
                })()}
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  className={`btn btn-xs ${(() => {
                    const whenObj = (t.when || {}) as Record<string, unknown>;
                    return typeof whenObj.yes_no === 'string' && Boolean(whenObj.yes_no);
                  })()
                    ? 'btn-primary'
                    : 'btn-secondary'}`}
                  onClick={() => onUpdateTransitionWhen(tIdx, { yes_no: 'yes' })}
                  disabled={disabled}
                >
                  yes/no
                </button>
                {(() => {
                  const whenObj = (t.when || {}) as Record<string, unknown>;
                  const yesNoVal = typeof whenObj.yes_no === 'string' ? (whenObj.yes_no as string) : '';
                  if (!yesNoVal) return null;
                  return (
                    <select
                      className="select select-sm"
                      value={yesNoVal}
                      onChange={(e) => onUpdateTransitionWhen(tIdx, { yes_no: e.target.value })}
                      disabled={disabled}
                    >
                      <option value="yes">yes</option>
                      <option value="no">no</option>
                    </select>
                  );
                })()}
              </div>
            </div>
          </div>

          <div className="md:col-span-1 flex items-center justify-end gap-2">
            <button type="button" className="btn btn-xs btn-secondary" onClick={() => onRemoveTransition(tIdx)} disabled={disabled}>
              Remover
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
