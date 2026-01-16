import React from 'react';

type NodeItem = {
  id: string;
  type: string;
};

type Props = {
  nodes: NodeItem[];
  selectedNodeId: string;
  startNodeId: string;
  getNodeTypeLabel: (nodeType: string) => string;
  onAddNode: () => void;
  onSelectNode: (nodeId: string) => void;
  onChangeStartNode: (nodeId: string) => void;
  disabled: boolean;
};

export function FlowNodesSidebar({
  nodes,
  selectedNodeId,
  startNodeId,
  getNodeTypeLabel,
  onAddNode,
  onSelectNode,
  onChangeStartNode,
  disabled,
}: Props) {
  return (
    <div className="md:col-span-2 bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-700">Nós</div>
        <button type="button" className="btn btn-sm btn-secondary" onClick={onAddNode} disabled={disabled}>
          + Nó
        </button>
      </div>

      <div className="space-y-1 max-h-[420px] overflow-auto">
        {nodes.map((n) => (
          <button
            key={n.id}
            type="button"
            className={`w-full text-left px-3 py-2 rounded border ${selectedNodeId === n.id ? 'border-blue-500 bg-white' : 'border-slate-200 bg-white hover:border-slate-300'}`}
            onClick={() => onSelectNode(n.id)}
            disabled={disabled}
          >
            <div className="flex justify-between items-center gap-2 text-xs">
              <span className="font-mono text-slate-700">{n.id}</span>
              <span className="text-slate-500">{getNodeTypeLabel(n.type) || n.type}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-3">
        <label className="block text-xs font-semibold text-slate-600">Nó inicial</label>
        <select className="select w-full" value={startNodeId} onChange={(e) => onChangeStartNode(e.target.value)} disabled={disabled}>
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.id}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
