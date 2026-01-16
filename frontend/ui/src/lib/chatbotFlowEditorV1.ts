import {
  type ChatbotFlowDefinitionV1,
  type FlowNodeV1,
  type FlowTransitionV1,
  defaultDefinition,
  normalizeDefinition,
  splitCommaList,
  validateDefinition,
} from './chatbotFlowDefinitionV1';

import { removeNodeFromDefinition, renameNodeInDefinition, updateNodeInDefinition } from './chatbotFlowMutationsV1';

export type FlowEditAction =
  | {
      kind: 'create_node';
      id: string;
      nodeType: string;
      prompt?: string;
    }
  | {
      kind: 'create_basic_flow';
    }
  | {
      kind: 'insert_lgpd_intro';
      text?: string;
    }
  | {
      kind: 'remove_node';
      id: string;
    }
  | {
      kind: 'rename_node';
      from: string;
      to: string;
    }
  | {
      kind: 'set_transition_default';
      from: string;
      to: string;
    }
  | {
      kind: 'set_transition_contains_any';
      from: string;
      to: string;
      values: string[];
    }
  | {
      kind: 'set_transition_equals_any';
      from: string;
      to: string;
      values: string[];
    }
  | {
      kind: 'set_transition_yes_no';
      from: string;
      to: string;
      value: 'yes' | 'no';
    }
  | {
      kind: 'set_transition_schedule_intent';
      from: string;
      to: string;
    }
  | {
      kind: 'set_start';
      nodeId: string;
    }
  | {
      kind: 'set_node_prompt';
      nodeId: string;
      prompt: string;
    }
  | {
      kind: 'set_node_type';
      nodeId: string;
      nodeType: string;
    }
  | {
      kind: 'set_node_handler';
      nodeId: string;
      handler?: string;
    };

export type ParseFlowCommandsResult =
  | {
      ok: true;
      actions: FlowEditAction[];
      warnings: string[];
    }
  | {
      ok: false;
      error: string;
    };

function normalizeId(raw: string): string {
  return (raw || '').trim();
}

function unquote(raw: string): string {
  const s = (raw || '').trim();
  if (s.startsWith('"') && s.endsWith('"') && s.length >= 2) return s.slice(1, -1);
  return s;
}

function defaultLgpdText(): string {
  return 'Aviso de Privacidade (LGPD): Ao continuar, você concorda que seus dados serão usados para atendimento e registro do seu interesse. Você pode solicitar remoção/alteração a qualquer momento.';
}

function lgpdShortText(): string {
  return 'Aviso LGPD: seus dados serão usados apenas para atendimento. Você pode solicitar alteração/remoção a qualquer momento.';
}

function lgpdFullText(): string {
  return (
    'Aviso de Privacidade (LGPD): Ao continuar, você concorda que seus dados pessoais serão utilizados para atendimento, registro do seu interesse e eventual contato sobre imóveis. ' +
    'Você pode solicitar acesso, correção, portabilidade ou exclusão dos seus dados a qualquer momento. '
  );
}

function resolveLgpdTextFromArg(rawArg: string | undefined): string | undefined {
  const raw = (rawArg || '').trim();
  if (!raw) return undefined;
  const lower = raw.toLowerCase();
  if (lower === 'curto') return lgpdShortText();
  if (lower === 'completo') return lgpdFullText();
  return unquote(raw);
}

function normalizeValuesList(raw: string): string[] {
  return splitCommaList(unquote(raw))
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);
}

export function parseFlowCommands(rawText: string): ParseFlowCommandsResult {
  const warnings: string[] = [];
  const actions: FlowEditAction[] = [];

  const lines = (rawText || '')
    .split(/\r?\n/g)
    .map((l) => l.trim())
    .filter((l) => Boolean(l));

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] || '';

    {
      const m = line.match(/^criar\s+fluxo\s+b[áa]sico$/i);
      if (m) {
        actions.push({ kind: 'create_basic_flow' });
        continue;
      }
    }

    {
      const m = line.match(/^inserir\s+lgpd(?:\s+(.+))?$/i);
      if (m) {
        const raw = m[1] ? String(m[1]) : undefined;
        const text = resolveLgpdTextFromArg(raw);
        actions.push({ kind: 'insert_lgpd_intro', text });
        continue;
      }
    }

    {
      const m = line.match(/^criar\s+n[óo]\s+(\S+)\s+mensagem\s+(.+)$/i);
      if (m) {
        const id = normalizeId(m[1] || '');
        const msgRaw = String(m[2] || '');
        const prompt = unquote(msgRaw);
        if (!id) return { ok: false, error: `Linha ${i + 1}: id do nó é obrigatório.` };
        actions.push({ kind: 'create_node', id, nodeType: 'static_message', prompt });
        continue;
      }
    }

    {
      const m = line.match(/^criar\s+n[óo]\s+(\S+)\s+fim$/i);
      if (m) {
        const id = normalizeId(m[1] || '');
        if (!id) return { ok: false, error: `Linha ${i + 1}: id do nó é obrigatório.` };
        actions.push({ kind: 'create_node', id, nodeType: 'end' });
        continue;
      }
    }

    {
      const m = line.match(/^criar\s+n[óo]\s+(\S+)\s+prompt\s+(.+)$/i);
      if (m) {
        const id = normalizeId(m[1] || '');
        const promptRaw = String(m[2] || '');
        const prompt = unquote(promptRaw);
        if (!id) return { ok: false, error: `Linha ${i + 1}: id do nó é obrigatório.` };
        actions.push({ kind: 'create_node', id, nodeType: 'prompt_and_branch', prompt });
        continue;
      }
    }

    {
      const m = line.match(/^criar\s+n[óo]\s+(\S+)\s+do\s+tipo\s+(\S+)(?:\s+prompt\s+(.+))?$/i);
      if (m) {
        const id = normalizeId(m[1] || '');
        const nodeType = normalizeId(m[2] || '');
        const promptRaw = m[3] ? String(m[3]) : '';
        const prompt = promptRaw ? unquote(promptRaw) : undefined;
        if (!id) return { ok: false, error: `Linha ${i + 1}: id do nó é obrigatório.` };
        if (!nodeType) return { ok: false, error: `Linha ${i + 1}: tipo do nó é obrigatório.` };
        actions.push({ kind: 'create_node', id, nodeType, prompt });
        continue;
      }
    }

    {
      const m = line.match(/^(?:no|n[óo])\s+(\S+)\s*->\s*(\S+)\s+default$/i);
      if (m) {
        const from = normalizeId(m[1] || '');
        const to = normalizeId(m[2] || '');
        if (!from || !to) return { ok: false, error: `Linha ${i + 1}: origem e destino são obrigatórios.` };
        actions.push({ kind: 'set_transition_default', from, to });
        continue;
      }
    }

    {
      const m = line.match(/^(?:no|n[óo])\s+(\S+)\s*->\s*(\S+)\s+(?:contains_any|cont[eé]m)\s+(.+)$/i);
      if (m) {
        const from = normalizeId(m[1] || '');
        const to = normalizeId(m[2] || '');
        const rawList = String(m[3] || '');
        const values = normalizeValuesList(rawList);
        if (!from || !to) return { ok: false, error: `Linha ${i + 1}: origem e destino são obrigatórios.` };
        if (values.length === 0) return { ok: false, error: `Linha ${i + 1}: contains_any precisa de ao menos 1 valor.` };
        actions.push({ kind: 'set_transition_contains_any', from, to, values });
        continue;
      }
    }

    {
      const m = line.match(/^(?:no|n[óo])\s+(\S+)\s*->\s*(\S+)\s+(?:equals_any|igual)\s+(.+)$/i);
      if (m) {
        const from = normalizeId(m[1] || '');
        const to = normalizeId(m[2] || '');
        const rawList = String(m[3] || '');
        const values = normalizeValuesList(rawList);
        if (!from || !to) return { ok: false, error: `Linha ${i + 1}: origem e destino são obrigatórios.` };
        if (values.length === 0) return { ok: false, error: `Linha ${i + 1}: equals_any precisa de ao menos 1 valor.` };
        actions.push({ kind: 'set_transition_equals_any', from, to, values });
        continue;
      }
    }

    {
      const m = line.match(/^(?:no|n[óo])\s+(\S+)\s*->\s*(\S+)\s+(?:se\s+)?(yes|no|sim|n[ãa]o)$/i);
      if (m) {
        const from = normalizeId(m[1] || '');
        const to = normalizeId(m[2] || '');
        const raw = normalizeId(m[3] || '').toLowerCase();
        const value = (raw === 'sim' ? 'yes' : raw === 'não' || raw === 'nao' ? 'no' : raw) as 'yes' | 'no';
        if (!from || !to) return { ok: false, error: `Linha ${i + 1}: origem e destino são obrigatórios.` };
        actions.push({ kind: 'set_transition_yes_no', from, to, value });
        continue;
      }
    }

    {
      const m = line.match(/^(?:no|n[óo])\s+(\S+)\s*->\s*(\S+)\s+(?:schedule_intent|agendar)$/i);
      if (m) {
        const from = normalizeId(m[1] || '');
        const to = normalizeId(m[2] || '');
        if (!from || !to) return { ok: false, error: `Linha ${i + 1}: origem e destino são obrigatórios.` };
        actions.push({ kind: 'set_transition_schedule_intent', from, to });
        continue;
      }
    }

    {
      const m = line.match(/^start\s*->\s*(\S+)$/i);
      if (m) {
        const nodeId = normalizeId(m[1] || '');
        if (!nodeId) return { ok: false, error: `Linha ${i + 1}: nodeId é obrigatório.` };
        actions.push({ kind: 'set_start', nodeId });
        continue;
      }
    }

    {
      const m = line.match(/^(?:no|n[óo])\s+(\S+)\s+prompt\s+(.+)$/i);
      if (m) {
        const nodeId = normalizeId(m[1] || '');
        const prompt = unquote(String(m[2] || ''));
        if (!nodeId) return { ok: false, error: `Linha ${i + 1}: nodeId é obrigatório.` };
        actions.push({ kind: 'set_node_prompt', nodeId, prompt });
        continue;
      }
    }

    {
      const m = line.match(/^(?:no|n[óo])\s+(\S+)\s+tipo\s+(\S+)$/i);
      if (m) {
        const nodeId = normalizeId(m[1] || '');
        const nodeType = normalizeId(m[2] || '');
        if (!nodeId) return { ok: false, error: `Linha ${i + 1}: nodeId é obrigatório.` };
        if (!nodeType) return { ok: false, error: `Linha ${i + 1}: tipo é obrigatório.` };
        actions.push({ kind: 'set_node_type', nodeId, nodeType });
        continue;
      }
    }

    {
      const m = line.match(/^(?:no|n[óo])\s+(\S+)\s+handler\s+(.+)$/i);
      if (m) {
        const nodeId = normalizeId(m[1] || '');
        const handlerRaw = normalizeId(String(m[2] || ''));
        if (!nodeId) return { ok: false, error: `Linha ${i + 1}: nodeId é obrigatório.` };
        const handler = handlerRaw ? handlerRaw : undefined;
        actions.push({ kind: 'set_node_handler', nodeId, handler });
        continue;
      }
    }

    {
      const m = line.match(/^remover\s+n[óo]\s+(\S+)$/i);
      if (m) {
        const id = normalizeId(m[1] || '');
        if (!id) return { ok: false, error: `Linha ${i + 1}: id do nó é obrigatório.` };
        actions.push({ kind: 'remove_node', id });
        continue;
      }
    }

    {
      const m = line.match(/^renomear\s+n[óo]\s+(\S+)\s+para\s+(\S+)$/i);
      if (m) {
        const from = normalizeId(m[1] || '');
        const to = normalizeId(m[2] || '');
        if (!from || !to) return { ok: false, error: `Linha ${i + 1}: origem e destino são obrigatórios.` };
        actions.push({ kind: 'rename_node', from, to });
        continue;
      }
    }

    return {
      ok: false,
      error:
        `Linha ${i + 1}: comando não reconhecido: "${line}". ` +
        `Use: criar fluxo básico | inserir lgpd [curto|completo|"..."] | criar nó <id> mensagem "..." | criar nó <id> prompt "..." | criar nó <id> fim | criar nó <id> do tipo <tipo> [prompt "..."] | start -> <nodeId> | no/nó <id> prompt "..." | no/nó <id> tipo <tipo> | no/nó <id> handler <handler> | no/nó <from> -> <to> default | no/nó <from> -> <to> contém "a,b" | no/nó <from> -> <to> igual "a,b" | no/nó <from> -> <to> se sim|se não | no/nó <from> -> <to> agendar | remover nó <id> | renomear nó <from> para <to>`,
    };
  }

  if (actions.length === 0) return { ok: false, error: 'Nenhum comando encontrado.' };
  return { ok: true, actions, warnings };
}

export type ApplyFlowEditActionsResult =
  | {
      ok: true;
      definition: ChatbotFlowDefinitionV1;
      applied: string[];
      suggestedSelectedNodeId?: string;
    }
  | {
      ok: false;
      error: string;
    };

export type PreviewFlowCommandsResult =
  | {
      ok: true;
      definition: ChatbotFlowDefinitionV1;
      applied: string[];
      suggestedSelectedNodeId?: string;
    }
  | {
      ok: false;
      error: string;
    };

function ensureNodeExists(def: ChatbotFlowDefinitionV1, nodeId: string): FlowNodeV1 | null {
  return (def.nodes || []).find((n) => n.id === nodeId) || null;
}

function findNodeIndex(def: ChatbotFlowDefinitionV1, nodeId: string): number {
  return (def.nodes || []).findIndex((n) => n.id === nodeId);
}

function createUniqueNodeId(def: ChatbotFlowDefinitionV1, preferred: string): string {
  const base = normalizeId(preferred) || 'node';
  const used = new Set((def.nodes || []).map((n) => (n.id || '').trim()).filter(Boolean));
  if (!used.has(base)) return base;
  for (let i = 2; i < 999; i++) {
    const c = `${base}_${i}`;
    if (!used.has(c)) return c;
  }
  return `${base}_${Date.now()}`;
}

function resolveExistingLgpdNodeId(def: ChatbotFlowDefinitionV1): string | null {
  const exact = ensureNodeExists(def, 'lgpd');
  if (exact) return 'lgpd';

  const ids = (def.nodes || [])
    .map((n) => (n.id || '').trim())
    .filter(Boolean)
    .filter((id) => /^lgpd(_\d+)?$/i.test(id));

  if (ids.length === 0) return null;
  ids.sort();
  return ids[0] || null;
}

function resolveExistingEndNodeId(def: ChatbotFlowDefinitionV1): string | null {
  const exact = ensureNodeExists(def, 'end');
  if (exact) return 'end';
  const endNode = (def.nodes || []).find((n) => n.type === 'end');
  return endNode?.id || null;
}

function lgpdConsentPrompt(): string {
  return 'Você concorda com o uso dos seus dados para atendimento? Responda "sim" para continuar ou "não" para encerrar.';
}

function lgpdCombinedPrompt(lgpdText: string): string {
  const t = (lgpdText || '').trim();
  const s = lgpdConsentPrompt();
  if (!t) return s;
  return `${t}\n\n${s}`;
}

function upsertDefaultTransition(node: FlowNodeV1, to: string): FlowNodeV1 {
  const transitions = Array.isArray(node.transitions) ? [...node.transitions] : [];

  const defaultIdx = transitions.findIndex((t) => !t.when || Object.keys(t.when).length === 0);
  const nextT: FlowTransitionV1 = { to };

  if (defaultIdx >= 0) {
    transitions[defaultIdx] = nextT;
  } else {
    transitions.push(nextT);
  }

  return { ...node, transitions };
}

function whenSignature(when: Record<string, unknown>): string {
  const keys = Object.keys(when).sort();
  const normalized: Record<string, unknown> = {};
  for (const k of keys) normalized[k] = when[k];
  return JSON.stringify(normalized);
}

function upsertTransitionByWhen(node: FlowNodeV1, to: string, when: Record<string, unknown>): FlowNodeV1 {
  const transitions = Array.isArray(node.transitions) ? [...node.transitions] : [];
  const sig = whenSignature(when);
  const idx = transitions.findIndex((t) => whenSignature((t.when || {}) as Record<string, unknown>) === sig);
  const nextT: FlowTransitionV1 = { to, when };
  if (idx >= 0) {
    transitions[idx] = nextT;
  } else {
    transitions.push(nextT);
  }
  return { ...node, transitions };
}

export function applyFlowEditActions(def: ChatbotFlowDefinitionV1, actions: FlowEditAction[]): ApplyFlowEditActionsResult {
  let next: ChatbotFlowDefinitionV1 = normalizeDefinition(def);
  const applied: string[] = [];
  let suggestedSelectedNodeId: string | undefined;

  for (const a of actions) {
    if (a.kind === 'create_basic_flow') {
      const base = defaultDefinition();
      const nodes: FlowNodeV1[] = [
        {
          id: 'lgpd',
          type: 'prompt_and_branch',
          prompt: lgpdCombinedPrompt(defaultLgpdText()),
          transitions: [
            { to: 'welcome', when: { yes_no: 'yes' } },
            { to: 'end', when: { yes_no: 'no' } },
          ],
        },
        {
          id: 'welcome',
          type: 'static_message',
          prompt: 'Olá! Para te atender melhor, vou fazer algumas perguntas rápidas.',
          transitions: [{ to: 'ask_name' }],
        },
        {
          id: 'ask_name',
          type: 'capture_text',
          prompt: 'Qual é o seu nome?',
          config: { target: 'lead.name', min_len: 2 },
          transitions: [{ to: 'ask_phone' }],
        },
        {
          id: 'ask_phone',
          type: 'capture_phone_generic',
          prompt: 'Qual é o seu WhatsApp (com DDD)?',
          config: { target: 'lead.phone', min_digits: 10, max_digits: 13 },
          transitions: [{ to: 'thanks' }],
        },
        {
          id: 'thanks',
          type: 'static_message',
          prompt: 'Obrigado! Já registramos seus dados e vamos te atender em seguida.',
          transitions: [{ to: 'end' }],
        },
        {
          id: 'end',
          type: 'end',
          transitions: [],
        },
      ];

      next = normalizeDefinition({ ...base, start: 'lgpd', nodes });
      applied.push('= flow básico criado');
      suggestedSelectedNodeId = 'welcome';
      continue;
    }

    if (a.kind === 'insert_lgpd_intro') {
      const previousStart = normalizeId(next.start) || 'start';

      const existingLgpdId = resolveExistingLgpdNodeId(next);
      const lgpdId = existingLgpdId || createUniqueNodeId(next, 'lgpd');
      const lgpdText = a.text ? String(a.text) : defaultLgpdText();

      const existingEndId = resolveExistingEndNodeId(next);
      const endId = existingEndId || createUniqueNodeId(next, 'end');

      const combinedPrompt = lgpdCombinedPrompt(lgpdText);

      if (!ensureNodeExists(next, lgpdId)) {
        const newNode: FlowNodeV1 = {
          id: lgpdId,
          type: 'prompt_and_branch',
          prompt: combinedPrompt,
          transitions: [],
        };
        next = { ...next, nodes: [...(next.nodes || []), newNode] };
        applied.push(`+ nó ${lgpdId} (lgpd)`);
      } else {
        const idx = findNodeIndex(next, lgpdId);
        if (idx >= 0) {
          next = updateNodeInDefinition(next, idx, { type: 'prompt_and_branch', prompt: combinedPrompt });
          applied.push(`~ lgpd texto (${lgpdId})`);
        }
      }

      if (!ensureNodeExists(next, endId)) {
        const endNode: FlowNodeV1 = { id: endId, type: 'end', transitions: [] };
        next = { ...next, nodes: [...(next.nodes || []), endNode] };
        applied.push(`+ nó ${endId} (end)`);
      }

      // Evita loop do MCP sobrescrever a mensagem do LGPD:
      // Mantemos LGPD + pergunta em um único prompt_and_branch.
      const to = previousStart === lgpdId
        ? (next.nodes || []).find((n) => n.id !== lgpdId)?.id || previousStart
        : previousStart;

      next = {
        ...next,
        start: lgpdId,
        nodes: (next.nodes || []).map((n) => {
          if (n.id !== lgpdId) return n;
          return {
            ...n,
            type: 'prompt_and_branch',
            prompt: combinedPrompt,
            transitions: [
              { to, when: { yes_no: 'yes' } },
              { to: endId, when: { yes_no: 'no' } },
            ],
          };
        }),
      };

      applied.push(`~ start -> ${lgpdId}`);
      applied.push(`~ transições consentimento: ${lgpdId} (sim->${to}, não->${endId})`);
      suggestedSelectedNodeId = lgpdId;
      continue;
    }

    if (a.kind === 'create_node') {
      const id = normalizeId(a.id);
      const nodeType = normalizeId(a.nodeType);
      if (!id) return { ok: false, error: 'create_node: id inválido.' };
      if (!nodeType) return { ok: false, error: `create_node(${id}): tipo inválido.` };
      if (ensureNodeExists(next, id)) return { ok: false, error: `Nó já existe: ${id}` };

      const newNode: FlowNodeV1 = {
        id,
        type: nodeType,
        prompt: a.prompt ? String(a.prompt) : undefined,
        transitions: [],
      };

      next = { ...next, nodes: [...(next.nodes || []), newNode] };
      applied.push(`+ nó ${id} (${nodeType})`);
      suggestedSelectedNodeId = id;
      continue;
    }

    if (a.kind === 'remove_node') {
      const id = normalizeId(a.id);
      if (!id) return { ok: false, error: 'remove_node: id inválido.' };
      if (!ensureNodeExists(next, id)) return { ok: false, error: `Nó não existe: ${id}` };
      const res = removeNodeFromDefinition(next, id);
      next = res.definition;
      applied.push(`- nó ${id}`);
      suggestedSelectedNodeId = res.nextSelectedNodeId;
      continue;
    }

    if (a.kind === 'rename_node') {
      const from = normalizeId(a.from);
      const to = normalizeId(a.to);
      if (!from || !to) return { ok: false, error: 'rename_node: origem/destino inválidos.' };
      if (!ensureNodeExists(next, from)) return { ok: false, error: `Nó não existe: ${from}` };
      if (from !== to && ensureNodeExists(next, to)) return { ok: false, error: `Já existe um nó com id: ${to}` };
      const res = renameNodeInDefinition(next, from, to);
      next = res.definition;
      applied.push(`~ renomear nó: ${from} -> ${to}`);
      suggestedSelectedNodeId = res.nextSelectedNodeId;
      continue;
    }

    if (a.kind === 'set_transition_default') {
      const from = normalizeId(a.from);
      const to = normalizeId(a.to);
      if (!from || !to) return { ok: false, error: 'set_transition_default: origem/destino inválidos.' };

      const fromNode = ensureNodeExists(next, from);
      const toNode = ensureNodeExists(next, to);
      if (!fromNode) return { ok: false, error: `Nó de origem não existe: ${from}` };
      if (!toNode) return { ok: false, error: `Nó de destino não existe: ${to}` };

      next = {
        ...next,
        nodes: (next.nodes || []).map((n) => (n.id === from ? upsertDefaultTransition(n, to) : n)),
      };
      applied.push(`~ transição default: ${from} -> ${to}`);
      continue;
    }

    if (a.kind === 'set_transition_contains_any') {
      const from = normalizeId(a.from);
      const to = normalizeId(a.to);
      const values = Array.isArray(a.values) ? a.values : [];
      if (!from || !to) return { ok: false, error: 'set_transition_contains_any: origem/destino inválidos.' };
      if (values.length === 0) return { ok: false, error: 'set_transition_contains_any: precisa de valores.' };

      const fromNode = ensureNodeExists(next, from);
      const toNode = ensureNodeExists(next, to);
      if (!fromNode) return { ok: false, error: `Nó de origem não existe: ${from}` };
      if (!toNode) return { ok: false, error: `Nó de destino não existe: ${to}` };

      next = {
        ...next,
        nodes: (next.nodes || []).map((n) =>
          n.id === from ? upsertTransitionByWhen(n, to, { contains_any: values }) : n,
        ),
      };
      applied.push(`~ transição contains_any: ${from} -> ${to}`);
      continue;
    }

    if (a.kind === 'set_transition_equals_any') {
      const from = normalizeId(a.from);
      const to = normalizeId(a.to);
      const values = Array.isArray(a.values) ? a.values : [];
      if (!from || !to) return { ok: false, error: 'set_transition_equals_any: origem/destino inválidos.' };
      if (values.length === 0) return { ok: false, error: 'set_transition_equals_any: precisa de valores.' };

      const fromNode = ensureNodeExists(next, from);
      const toNode = ensureNodeExists(next, to);
      if (!fromNode) return { ok: false, error: `Nó de origem não existe: ${from}` };
      if (!toNode) return { ok: false, error: `Nó de destino não existe: ${to}` };

      next = {
        ...next,
        nodes: (next.nodes || []).map((n) =>
          n.id === from ? upsertTransitionByWhen(n, to, { equals_any: values }) : n,
        ),
      };
      applied.push(`~ transição equals_any: ${from} -> ${to}`);
      continue;
    }

    if (a.kind === 'set_transition_yes_no') {
      const from = normalizeId(a.from);
      const to = normalizeId(a.to);
      const value = a.value;
      if (!from || !to) return { ok: false, error: 'set_transition_yes_no: origem/destino inválidos.' };

      const fromNode = ensureNodeExists(next, from);
      const toNode = ensureNodeExists(next, to);
      if (!fromNode) return { ok: false, error: `Nó de origem não existe: ${from}` };
      if (!toNode) return { ok: false, error: `Nó de destino não existe: ${to}` };

      next = {
        ...next,
        nodes: (next.nodes || []).map((n) =>
          n.id === from ? upsertTransitionByWhen(n, to, { yes_no: value }) : n,
        ),
      };
      applied.push(`~ transição yes_no(${value}): ${from} -> ${to}`);
      continue;
    }

    if (a.kind === 'set_transition_schedule_intent') {
      const from = normalizeId(a.from);
      const to = normalizeId(a.to);
      if (!from || !to) return { ok: false, error: 'set_transition_schedule_intent: origem/destino inválidos.' };

      const fromNode = ensureNodeExists(next, from);
      const toNode = ensureNodeExists(next, to);
      if (!fromNode) return { ok: false, error: `Nó de origem não existe: ${from}` };
      if (!toNode) return { ok: false, error: `Nó de destino não existe: ${to}` };

      next = {
        ...next,
        nodes: (next.nodes || []).map((n) =>
          n.id === from ? upsertTransitionByWhen(n, to, { schedule_intent: true }) : n,
        ),
      };
      applied.push(`~ transição schedule_intent: ${from} -> ${to}`);
      continue;
    }

    if (a.kind === 'set_start') {
      const nodeId = normalizeId(a.nodeId);
      if (!nodeId) return { ok: false, error: 'set_start: nodeId inválido.' };
      if (!ensureNodeExists(next, nodeId)) return { ok: false, error: `Nó não existe: ${nodeId}` };
      next = { ...next, start: nodeId };
      applied.push(`~ start -> ${nodeId}`);
      suggestedSelectedNodeId = nodeId;
      continue;
    }

    if (a.kind === 'set_node_prompt') {
      const nodeId = normalizeId(a.nodeId);
      if (!nodeId) return { ok: false, error: 'set_node_prompt: nodeId inválido.' };
      const idx = findNodeIndex(next, nodeId);
      if (idx < 0) return { ok: false, error: `Nó não existe: ${nodeId}` };
      next = updateNodeInDefinition(next, idx, { prompt: String(a.prompt || '') });
      applied.push(`~ prompt(${nodeId})`);
      suggestedSelectedNodeId = nodeId;
      continue;
    }

    if (a.kind === 'set_node_type') {
      const nodeId = normalizeId(a.nodeId);
      const nodeType = normalizeId(a.nodeType);
      if (!nodeId || !nodeType) return { ok: false, error: 'set_node_type: nodeId/tipo inválidos.' };
      const idx = findNodeIndex(next, nodeId);
      if (idx < 0) return { ok: false, error: `Nó não existe: ${nodeId}` };
      next = updateNodeInDefinition(next, idx, { type: nodeType });
      applied.push(`~ tipo(${nodeId}) -> ${nodeType}`);
      suggestedSelectedNodeId = nodeId;
      continue;
    }

    if (a.kind === 'set_node_handler') {
      const nodeId = normalizeId(a.nodeId);
      if (!nodeId) return { ok: false, error: 'set_node_handler: nodeId inválido.' };
      const idx = findNodeIndex(next, nodeId);
      if (idx < 0) return { ok: false, error: `Nó não existe: ${nodeId}` };
      next = updateNodeInDefinition(next, idx, { handler: a.handler ? String(a.handler) : undefined });
      applied.push(`~ handler(${nodeId})`);
      suggestedSelectedNodeId = nodeId;
      continue;
    }

    const neverAction: never = a;
    return { ok: false, error: `Ação não suportada: ${String(neverAction)}` };
  }

  next = normalizeDefinition(next);

  return { ok: true, definition: next, applied, suggestedSelectedNodeId };
}

export function previewFlowCommands(def: ChatbotFlowDefinitionV1, rawText: string): PreviewFlowCommandsResult {
  const parsed = parseFlowCommands(rawText);
  if (!parsed.ok) return { ok: false, error: parsed.error };

  const appliedRes = applyFlowEditActions(def, parsed.actions);
  if (!appliedRes.ok) return { ok: false, error: appliedRes.error };

  const errs = validateDefinition(appliedRes.definition);
  if (errs.length > 0) return { ok: false, error: `Validação falhou: ${errs[0]}` };

  return {
    ok: true,
    definition: appliedRes.definition,
    applied: appliedRes.applied,
    suggestedSelectedNodeId: appliedRes.suggestedSelectedNodeId,
  };
}
