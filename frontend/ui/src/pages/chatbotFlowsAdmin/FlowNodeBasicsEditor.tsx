import React from 'react';

type NodeTypeOption = {
  value: string;
  label: string;
};

type Props = {
  nodeId: string;
  startNodeId: string;
  nodeType: string;
  nodeTypeOptions: NodeTypeOption[];
  showCustomNodeTypeOption: boolean;
  handler: string;
  prompt: string;
  onRemove: () => void;
  onChangeNodeId: (next: string) => void;
  onChangeNodeType: (next: string) => void;
  onChangeHandler: (next: string) => void;
  onChangePrompt: (next: string) => void;
  disabled: boolean;
};

export function FlowNodeBasicsEditor({
  nodeId,
  startNodeId,
  nodeType,
  nodeTypeOptions,
  showCustomNodeTypeOption,
  handler,
  prompt,
  onRemove,
  onChangeNodeId,
  onChangeNodeType,
  onChangeHandler,
  onChangePrompt,
  disabled,
}: Props) {
  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold text-slate-800">Nó: {nodeId}</div>
        <button type="button" className="btn btn-sm btn-secondary" onClick={onRemove} disabled={disabled || nodeId === startNodeId}>
          Remover
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-semibold text-slate-600">Identificador</label>
          <input className="input" value={nodeId} onChange={(e) => onChangeNodeId(e.target.value)} disabled={disabled} />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-600">Tipo de nó</label>
          <select className="select w-full" value={nodeType} onChange={(e) => onChangeNodeType(e.target.value)} disabled={disabled}>
            {nodeTypeOptions.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
            {showCustomNodeTypeOption && <option value={nodeType}>Personalizado: {nodeType}</option>}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-600">Handler (avançado)</label>
          <input className="input" value={handler} onChange={(e) => onChangeHandler(e.target.value)} disabled={disabled} />
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-slate-600">Mensagem / Pergunta</label>
        <textarea className="input w-full" value={prompt} onChange={(e) => onChangePrompt(e.target.value)} disabled={disabled} />
      </div>
    </>
  );
}
