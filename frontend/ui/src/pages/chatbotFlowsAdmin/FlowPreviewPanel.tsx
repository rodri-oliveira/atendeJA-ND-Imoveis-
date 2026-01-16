import React from 'react';

type PreviewOut = { message: string; state: Record<string, unknown> };

type Props = {
  canPreview: boolean;
  previewInput: string;
  previewStateJson: string;
  previewLoading: boolean;
  previewOut: PreviewOut | null;
  onChangePreviewInput: (v: string) => void;
  onChangePreviewStateJson: (v: string) => void;
  onRunPreview: () => void;
  onResetPreview: () => void;
  disabled: boolean;
};

export function FlowPreviewPanel({
  canPreview,
  previewInput,
  previewStateJson,
  previewLoading,
  previewOut,
  onChangePreviewInput,
  onChangePreviewStateJson,
  onRunPreview,
  onResetPreview,
  disabled,
}: Props) {
  return (
    <div className="border-t border-slate-200 pt-4 space-y-2">
      <div className="text-sm font-semibold text-slate-700">Preview</div>
      {!canPreview ? (
        <div className="text-sm text-slate-500">Salve o flow primeiro para habilitar o preview.</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600">Input</label>
              <input className="input" value={previewInput} onChange={(e) => onChangePreviewInput(e.target.value)} disabled={previewLoading || disabled} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600">State (JSON)</label>
              <input
                className="input font-mono text-xs"
                value={previewStateJson}
                onChange={(e) => onChangePreviewStateJson(e.target.value)}
                disabled={previewLoading || disabled}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-secondary" onClick={onRunPreview} disabled={previewLoading || disabled}>
              {previewLoading ? 'Executando...' : 'Executar preview'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={onResetPreview} disabled={previewLoading || disabled}>
              Resetar conversa
            </button>
            <div className="text-xs text-slate-500 mt-2">Obs: preview usa a definição salva no backend. Salve para refletir alterações.</div>
          </div>
          {previewOut && (
            <div className="text-sm bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
              <div>
                <span className="font-semibold">Mensagem:</span> {previewOut.message}
              </div>
              <div>
                <div className="font-semibold">State:</div>
                <pre className="text-xs bg-white border border-slate-200 rounded p-2 overflow-auto">{JSON.stringify(previewOut.state, null, 2)}</pre>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
