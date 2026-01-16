import { apiFetch } from './auth';

export type ChatbotFlowDto = {
  id: number;
  tenant_id: number;
  domain: string;
  name: string;
  is_published: boolean;
  is_archived: boolean;
  published_version: number;
  published_at?: string | null;
  archived_at?: string | null;
  updated_at?: string | null;
  flow_definition?: unknown;
};

type ErrorBody = { detail?: string; message?: string };

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ErrorBody;
    const msg = body?.detail || body?.message;
    if (msg) return String(msg);
  } catch {
    // ignore
  }

  try {
    const text = await res.text();
    if (text) return text;
  } catch {
    // ignore
  }

  return `HTTP ${res.status}`;
}

export async function getTenantChatbotDomain(): Promise<string> {
  const res = await apiFetch('/admin/chatbot-domain');
  if (!res.ok) throw new Error(await readErrorDetail(res));
  const data = (await res.json()) as { domain?: string };
  return (data.domain || 'real_estate').trim() || 'real_estate';
}

export async function listFlowsForDomain(domain: string): Promise<ChatbotFlowDto[]> {
  const d = (domain || '').trim() || 'real_estate';
  const res = await apiFetch(`/admin/chatbot-flows?domain=${encodeURIComponent(d)}&include_archived=true`);
  if (!res.ok) throw new Error(`Flows: ${await readErrorDetail(res)}`);
  return (await res.json()) as ChatbotFlowDto[];
}

export async function getPublishedFlowForDomain(domain: string): Promise<ChatbotFlowDto | null> {
  const d = (domain || '').trim() || 'real_estate';
  const res = await apiFetch(`/admin/chatbot-flows/published?domain=${encodeURIComponent(d)}`);
  if (!res.ok) throw new Error(`Published: ${await readErrorDetail(res)}`);
  const data = (await res.json()) as { flow?: ChatbotFlowDto | null };
  return data.flow || null;
}

export async function getFlowById(flowId: number): Promise<ChatbotFlowDto> {
  const res = await apiFetch(`/admin/chatbot-flows/by-id/${flowId}`);
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return (await res.json()) as ChatbotFlowDto;
}

export async function createFromTemplate(input: {
  domain: string;
  template: string;
  name: string;
  overwrite: boolean;
  publish: boolean;
}): Promise<{ flow_id: number }> {
  const res = await apiFetch('/admin/chatbot-flows/create-from-template', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return (await res.json()) as { flow_id: number };
}

export async function cloneFlow(flowId: number, input: { name: string; overwrite: boolean; publish: boolean }): Promise<{ new_flow_id: number }> {
  const res = await apiFetch(`/admin/chatbot-flows/${flowId}/clone`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return (await res.json()) as { new_flow_id: number };
}

export async function setArchived(flowId: number, archived: boolean): Promise<void> {
  const res = await apiFetch(`/admin/chatbot-flows/${flowId}/${archived ? 'archive' : 'unarchive'}`, { method: 'POST' });
  if (!res.ok) throw new Error(await readErrorDetail(res));
}

export async function publishByVersion(input: { domain: string; published_version: number }): Promise<void> {
  const res = await apiFetch('/admin/chatbot-flows/publish-by-version', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
}

export async function saveFlow(input: { name: string; domain: string; flow_definition: unknown }): Promise<void> {
  const res = await apiFetch('/admin/chatbot-flows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
}

export async function publishFlow(flowId: number): Promise<void> {
  const res = await apiFetch(`/admin/chatbot-flows/${flowId}/publish`, { method: 'POST' });
  if (!res.ok) throw new Error(await readErrorDetail(res));
}

export async function previewFlow(flowId: number, input: { input: string; state: Record<string, unknown> }): Promise<{ message: string; state: Record<string, unknown> }> {
  const res = await apiFetch(`/admin/chatbot-flows/${flowId}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return (await res.json()) as { message: string; state: Record<string, unknown> };
}
