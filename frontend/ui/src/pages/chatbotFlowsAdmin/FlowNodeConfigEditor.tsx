import React from 'react';

type Props = {
  nodeType: string;
  cfg: Record<string, unknown>;
  advancedConfigJson: string;
  onUpdateConfigValue: (key: string, value: unknown) => void;
  onChangeAdvancedConfigRaw: (raw: string) => void;
  disabled: boolean;
};

export function FlowNodeConfigEditor({ nodeType, cfg, advancedConfigJson, onUpdateConfigValue, onChangeAdvancedConfigRaw, disabled }: Props) {
  return (
    <div>
      <label className="block text-xs font-semibold text-slate-600">Configuração do nó</label>
      {(() => {
        if (nodeType === 'capture_text') {
          return (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-semibold text-slate-600">Salvar em</label>
                <input
                  className="input font-mono text-xs"
                  value={String(cfg.target ?? '')}
                  onChange={(e) => onUpdateConfigValue('target', e.target.value)}
                  placeholder="car_dealer.query"
                  disabled={disabled}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600">Tamanho mínimo</label>
                <input
                  type="number"
                  className="input"
                  value={cfg.min_len === undefined ? '' : String(cfg.min_len)}
                  onChange={(e) => {
                    const v = e.target.value;
                    onUpdateConfigValue('min_len', v ? Number(v) : undefined);
                  }}
                  placeholder="2"
                  disabled={disabled}
                />
              </div>
            </div>
          );
        }

        if (nodeType === 'capture_number') {
          return (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <div className="md:col-span-2">
                <label className="block text-xs font-semibold text-slate-600">Salvar em</label>
                <input
                  className="input font-mono text-xs"
                  value={String(cfg.target ?? '')}
                  onChange={(e) => onUpdateConfigValue('target', e.target.value)}
                  placeholder="car_dealer.budget_max"
                  disabled={disabled}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600">Mínimo</label>
                <input
                  type="number"
                  className="input"
                  value={cfg.min === undefined ? '' : String(cfg.min)}
                  onChange={(e) => {
                    const v = e.target.value;
                    onUpdateConfigValue('min', v ? Number(v) : undefined);
                  }}
                  placeholder="1000"
                  disabled={disabled}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600">Máximo</label>
                <input
                  type="number"
                  className="input"
                  value={cfg.max === undefined ? '' : String(cfg.max)}
                  onChange={(e) => {
                    const v = e.target.value;
                    onUpdateConfigValue('max', v ? Number(v) : undefined);
                  }}
                  placeholder=""
                  disabled={disabled}
                />
              </div>
              <div className="md:col-span-4">
                <label className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <input
                    type="checkbox"
                    checked={Boolean(cfg.treat_as_thousands)}
                    onChange={(e) => onUpdateConfigValue('treat_as_thousands', e.target.checked)}
                    disabled={disabled}
                  />
                  Tratar valores pequenos como mil (treat_as_thousands)
                </label>
              </div>
            </div>
          );
        }

        if (nodeType === 'capture_phone_generic') {
          return (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <div className="md:col-span-2">
                <label className="block text-xs font-semibold text-slate-600">Salvar em</label>
                <input
                  className="input font-mono text-xs"
                  value={String(cfg.target ?? '')}
                  onChange={(e) => onUpdateConfigValue('target', e.target.value)}
                  placeholder="car_dealer.phone"
                  disabled={disabled}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600">Min dígitos</label>
                <input
                  type="number"
                  className="input"
                  value={cfg.min_digits === undefined ? '' : String(cfg.min_digits)}
                  onChange={(e) => {
                    const v = e.target.value;
                    onUpdateConfigValue('min_digits', v ? Number(v) : undefined);
                  }}
                  placeholder="10"
                  disabled={disabled}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600">Max dígitos</label>
                <input
                  type="number"
                  className="input"
                  value={cfg.max_digits === undefined ? '' : String(cfg.max_digits)}
                  onChange={(e) => {
                    const v = e.target.value;
                    onUpdateConfigValue('max_digits', v ? Number(v) : undefined);
                  }}
                  placeholder="13"
                  disabled={disabled}
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-xs font-semibold text-slate-600">Status do Lead (opcional)</label>
                <input
                  className="input"
                  value={String(cfg.lead_status ?? '')}
                  onChange={(e) => onUpdateConfigValue('lead_status', e.target.value)}
                  placeholder="novo"
                  disabled={disabled}
                />
              </div>
              <div className="md:col-span-4">
                <label className="block text-xs font-semibold text-slate-600">Mensagem para telefone inválido (opcional)</label>
                <input
                  className="input"
                  value={String(cfg.invalid_message ?? '')}
                  onChange={(e) => onUpdateConfigValue('invalid_message', e.target.value)}
                  placeholder="Telefone inválido. Envie com DDD."
                  disabled={disabled}
                />
              </div>
            </div>
          );
        }

        if (nodeType === 'execute_vehicle_search') {
          return (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div>
                <label className="block text-xs font-semibold text-slate-600">Caminho da busca (query)</label>
                <input
                  className="input font-mono text-xs"
                  value={String(cfg.query_path ?? '')}
                  onChange={(e) => onUpdateConfigValue('query_path', e.target.value)}
                  placeholder="car_dealer.query"
                  disabled={disabled}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600">Caminho do orçamento</label>
                <input
                  className="input font-mono text-xs"
                  value={String(cfg.budget_max_path ?? '')}
                  onChange={(e) => onUpdateConfigValue('budget_max_path', e.target.value)}
                  placeholder="car_dealer.budget_max"
                  disabled={disabled}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600">Caminho para salvar resultados</label>
                <input
                  className="input font-mono text-xs"
                  value={String(cfg.results_path ?? '')}
                  onChange={(e) => onUpdateConfigValue('results_path', e.target.value)}
                  placeholder="car_dealer.search_results"
                  disabled={disabled}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600">Quantidade de resultados</label>
                <input
                  type="number"
                  className="input"
                  value={cfg.limit === undefined ? '' : String(cfg.limit)}
                  onChange={(e) => {
                    const v = e.target.value;
                    onUpdateConfigValue('limit', v ? Number(v) : undefined);
                  }}
                  placeholder="3"
                  disabled={disabled}
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-xs font-semibold text-slate-600">Título da lista (opcional)</label>
                <input
                  className="input"
                  value={String(cfg.header ?? '')}
                  onChange={(e) => onUpdateConfigValue('header', e.target.value)}
                  placeholder="Encontrei essas opções:"
                  disabled={disabled}
                />
              </div>
              <div className="md:col-span-3">
                <label className="block text-xs font-semibold text-slate-600">Mensagem quando não houver resultados (opcional)</label>
                <input
                  className="input"
                  value={String(cfg.empty_message ?? '')}
                  onChange={(e) => onUpdateConfigValue('empty_message', e.target.value)}
                  placeholder="Não encontrei veículos com esse perfil."
                  disabled={disabled}
                />
              </div>
            </div>
          );
        }

        return <div className="text-xs text-slate-500">Este tipo de nó ainda não tem configuração por campos.</div>;
      })()}

      <details className="mt-2">
        <summary className="text-xs text-slate-600 cursor-pointer">Configuração avançada (técnico)</summary>
        <textarea
          className="input w-full font-mono text-xs mt-2"
          value={advancedConfigJson}
          onChange={(e) => onChangeAdvancedConfigRaw(e.target.value)}
          placeholder='{"target":"car_dealer.query","min_len":2}'
          disabled={disabled}
        />
      </details>
    </div>
  );
}
