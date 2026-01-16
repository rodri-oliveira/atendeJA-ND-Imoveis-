import React from 'react';

type LeadSummarySourceOption = {
  value: string;
  label: string;
};

type LeadSummaryField = {
  key: string;
  label: string;
  source: string;
  empty_value?: string | null;
};

type Props = {
  leadSummaryFields: LeadSummaryField[];
  leadSummarySourceOptions: LeadSummarySourceOption[];
  leadSummarySourceSuggestions: LeadSummarySourceOption[];
  onAddField: () => void;
  onUpdateField: (idx: number, patch: Partial<LeadSummaryField>) => void;
  onMoveField: (idx: number, dir: -1 | 1) => void;
  onRemoveField: (idx: number) => void;
  onAddSourceOption: () => void;
  onUpdateSourceOption: (idx: number, patch: Partial<LeadSummarySourceOption>) => void;
  onMoveSourceOption: (idx: number, dir: -1 | 1) => void;
  onRemoveSourceOption: (idx: number) => void;
  disabled: boolean;
};

export function FlowLeadSummaryEditor({
  leadSummaryFields,
  leadSummarySourceOptions,
  leadSummarySourceSuggestions,
  onAddField,
  onUpdateField,
  onMoveField,
  onRemoveField,
  onAddSourceOption,
  onUpdateSourceOption,
  onMoveSourceOption,
  onRemoveSourceOption,
  disabled,
}: Props) {
  return (
    <div className="border-t border-slate-200 pt-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-700">Resumo do Lead</div>
          <div className="text-xs text-slate-500">Define quais campos do state (preferences) aparecem no card/modal de Lead.</div>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onAddField} disabled={disabled}>
          + Campo
        </button>
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold text-slate-700">Opções do dropdown (Fonte / source)</div>
            <div className="text-xs text-slate-500">Você pode adicionar, remover e ordenar as opções exibidas no select.</div>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onAddSourceOption} disabled={disabled}>
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
                      onChange={(e) => onUpdateSourceOption(idx, { value: e.target.value })}
                      disabled={disabled}
                      placeholder="ex: city"
                    />
                  </div>
                  <div className="md:col-span-7">
                    <label className="block text-xs font-semibold text-slate-600">Label</label>
                    <input
                      className="input"
                      value={o.label}
                      onChange={(e) => onUpdateSourceOption(idx, { label: e.target.value })}
                      disabled={disabled}
                      placeholder="ex: Cidade"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 mt-2">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => onMoveSourceOption(idx, -1)} disabled={disabled || idx === 0}>
                    ↑
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => onMoveSourceOption(idx, 1)}
                    disabled={disabled || idx === leadSummarySourceOptions.length - 1}
                  >
                    ↓
                  </button>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => onRemoveSourceOption(idx)} disabled={disabled}>
                    Remover
                  </button>
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
                  <input className="input" value={f.key} onChange={(e) => onUpdateField(idx, { key: e.target.value })} disabled={disabled} />
                </div>
                <div className="md:col-span-3">
                  <label className="block text-xs font-semibold text-slate-600">Label</label>
                  <input className="input" value={f.label} onChange={(e) => onUpdateField(idx, { label: e.target.value })} disabled={disabled} />
                </div>
                <div className="md:col-span-4">
                  <label className="block text-xs font-semibold text-slate-600">Fonte (source)</label>
                  <div className="grid grid-cols-1 gap-2">
                    <select
                      className="select w-full"
                      value={leadSummarySourceSuggestions.some((x) => x.value === f.source) ? f.source : '__custom__'}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v === '__custom__') return;
                        onUpdateField(idx, { source: v });
                      }}
                      disabled={disabled}
                    >
                      {leadSummarySourceSuggestions.map((x) => (
                        <option key={x.value} value={x.value}>
                          {x.label}
                        </option>
                      ))}
                      <option value="__custom__">Personalizado…</option>
                    </select>

                    {(!f.source || !leadSummarySourceSuggestions.some((x) => x.value === f.source)) && (
                      <input
                        className="input font-mono text-xs"
                        value={f.source}
                        onChange={(e) => onUpdateField(idx, { source: e.target.value })}
                        disabled={disabled}
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
                    onChange={(e) => onUpdateField(idx, { empty_value: e.target.value || null })}
                    disabled={disabled}
                    placeholder="Ex: -"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 mt-2">
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onMoveField(idx, -1)} disabled={disabled || idx === 0}>
                  ↑
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onMoveField(idx, 1)} disabled={disabled || idx === leadSummaryFields.length - 1}>
                  ↓
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onRemoveField(idx)} disabled={disabled}>
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
