import React, { useMemo, useState } from 'react';

type Props = {
  commandText: string;
  onChangeCommandText: (next: string) => void;
  commandError: string | null;
  commandApplied: string[];
  nodeIdOptions: string[];
  previewError: string | null;
  previewLines: string[];
  onApply: () => void;
  onClear: () => void;
  disabled: boolean;
};

export function FlowCommandBar({
  commandText,
  onChangeCommandText,
  commandError,
  commandApplied,
  nodeIdOptions,
  previewError,
  previewLines,
  onApply,
  onClear,
  disabled,
}: Props) {
  const [showHelp, setShowHelp] = useState(false);
  const [nodeToInsert, setNodeToInsert] = useState('');

  const examples = useMemo(
    () =>
      [
        {
          label: 'Criar nó + start + default',
          text: 'criar nó asking_name prompt "Qual seu nome?"\nstart -> asking_name\nnó asking_name -> end default',
        },
        {
          label: 'Criar fluxo básico (template)',
          text: 'criar fluxo básico',
        },
        {
          label: 'Inserir LGPD no início',
          text: 'inserir lgpd',
        },
        {
          label: 'LGPD curto (preset)',
          text: 'inserir lgpd curto',
        },
        {
          label: 'LGPD completo (preset)',
          text: 'inserir lgpd completo',
        },
        {
          label: 'LGPD com texto custom',
          text: 'inserir lgpd "Aviso LGPD: seus dados serão usados apenas para atendimento. Você pode pedir remoção."',
        },
        {
          label: 'Mensagem + fim (ultra simples)',
          text: 'criar nó hello mensagem "Olá!"\ncriar nó end fim\nstart -> hello\nnó hello -> end default',
        },
        {
          label: 'Transição contém (texto)',
          text: 'nó asking_name -> end contém "tchau, sair"',
        },
        {
          label: 'Transição sim/não',
          text: 'nó confirm -> yes_node se sim\nnó confirm -> no_node se não',
        },
        {
          label: 'Transição agendar',
          text: 'nó start -> scheduling agendar',
        },
        {
          label: 'Editar nó (tipo/prompt/handler)',
          text: 'nó asking_name tipo prompt_and_branch\nnó asking_name prompt "Qual seu nome completo?"\nnó asking_name handler handle_asking_name',
        },
        {
          label: 'Renomear/remover nó',
          text: 'renomear nó asking_name para ask_name\nremover nó old_node',
        },
      ] as const,
    [],
  );

  function applyExampleText(text: string) {
    const base = (commandText || '').trimEnd();
    const next = base ? `${base}\n${text}` : text;
    onChangeCommandText(next);
  }

  function insertNodeId() {
    const id = (nodeToInsert || '').trim();
    if (!id) return;
    const base = (commandText || '').trimEnd();
    const next = base ? `${base}\nnó ${id} ` : `nó ${id} `;
    onChangeCommandText(next);
    setNodeToInsert('');
  }

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-slate-700">Comandos (português)</div>
          <div className="text-xs text-slate-500">Ex.: criar nó asking_name prompt &quot;Qual seu nome?&quot;</div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => setShowHelp((v) => !v)}
            disabled={disabled}
          >
            Ajuda
          </button>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={onClear}
            disabled={disabled || (!commandText.trim() && !commandError && commandApplied.length === 0)}
          >
            Limpar
          </button>
          <button type="button" className="btn btn-sm btn-primary" onClick={onApply} disabled={disabled || !commandText.trim()}>
            Aplicar
          </button>
        </div>
      </div>

      {showHelp && (
        <div className="border border-slate-200 bg-slate-50 rounded-lg p-3 space-y-2">
          <div className="text-xs text-slate-600">
            Você pode escrever uma linha por comando. Use <span className="font-mono">nó</span> ou <span className="font-mono">no</span>.
          </div>
          <div className="flex flex-wrap gap-2">
            {examples.map((ex) => (
              <button
                key={ex.label}
                type="button"
                className="btn btn-xs btn-secondary"
                onClick={() => applyExampleText(ex.text)}
                disabled={disabled}
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <textarea
        className="input w-full font-mono text-xs"
        rows={3}
        placeholder={'criar nó asking_name prompt "Qual seu nome?"\nno start -> asking_name default\nno asking_name -> end default'}
        value={commandText}
        onChange={(e) => onChangeCommandText(e.target.value)}
        disabled={disabled}
      />

      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[220px]">
          <div className="text-xs text-slate-500 mb-1">Inserir nó (atalho)</div>
          <input
            className="input w-full font-mono text-xs"
            list="flow-node-ids"
            value={nodeToInsert}
            onChange={(e) => setNodeToInsert(e.target.value)}
            placeholder="Ex: start"
            disabled={disabled}
          />
          <datalist id="flow-node-ids">
            {nodeIdOptions.map((id) => (
              <option key={id} value={id} />
            ))}
          </datalist>
        </div>
        <button type="button" className="btn btn-sm btn-secondary" onClick={insertNodeId} disabled={disabled || !nodeToInsert.trim()}>
          Inserir
        </button>
      </div>

      {previewError ? (
        <div className="text-xs text-red-600">{previewError}</div>
      ) : previewLines.length > 0 ? (
        <div className="text-xs text-slate-600">
          {previewLines.map((x, idx) => (
            <div key={idx}>{x}</div>
          ))}
        </div>
      ) : null}

      {commandError && <div className="text-xs text-red-600">{commandError}</div>}
      {commandApplied.length > 0 && (
        <div className="text-xs text-slate-600">
          {commandApplied.map((x, idx) => (
            <div key={idx}>{x}</div>
          ))}
        </div>
      )}
    </div>
  );
}
