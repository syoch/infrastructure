import { getToken } from './control_api.js';

const BASE = '/api/app-portal';

export interface WebApp {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  url?: string | null;
  project_directory: string;
  opencode_session_id: string;
  bridge_device_id: string;
  source: string;
  tags: string[];
  status: string;
  webui_url?: string | null;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
}

export interface AppFeedback {
  id: string;
  app_id: string;
  author?: string | null;
  body: string;
  kind: string;
  status: string;
  command_id?: string | null;
  target_session_id?: string | null;
  webui_url?: string | null;
  delivered_at?: string | null;
  error?: string | null;
  created_at: string;
}

export interface WebAppDetail extends WebApp {
  feedback: AppFeedback[];
}

export interface Bridge {
  device_id: string;
  hostname?: string | null;
  webui_base_url?: string | null;
  server_key?: string | null;
  last_seen?: string | null;
  registered_at: string;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail: string;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = await res.text();
    }
    const err = new Error(detail || `HTTP ${res.status}`);
    (err as Error & { status: number }).status = res.status;
    throw err;
  }
  if (res.status === 204) return null as T;
  return res.json();
}

export async function fetchWebApps(): Promise<WebApp[]> {
  const data = await req<{ apps: WebApp[] }>('GET', '/apps');
  return data.apps || [];
}

export async function fetchWebApp(slug: string): Promise<WebAppDetail> {
  return req<WebAppDetail>('GET', `/apps/${encodeURIComponent(slug)}`);
}

export interface CreateWebAppPayload {
  name: string;
  project_directory: string;
  opencode_session_id: string;
  description?: string;
  url?: string;
  slug?: string;
  tags?: string[];
}

export async function createWebApp(payload: CreateWebAppPayload): Promise<WebApp> {
  return req<WebApp>('POST', '/apps', payload);
}

export interface UpdateWebAppPayload {
  name?: string;
  description?: string | null;
  url?: string | null;
  project_directory?: string;
  opencode_session_id?: string;
  bridge_device_id?: string;
  tags?: string[];
  status?: string;
}

export async function updateWebApp(slug: string, patch: UpdateWebAppPayload): Promise<WebApp> {
  return req<WebApp>('PATCH', `/apps/${encodeURIComponent(slug)}`, patch);
}

export async function deleteWebApp(slug: string): Promise<{ status: string }> {
  return req('DELETE', `/apps/${encodeURIComponent(slug)}`);
}

export async function submitFeedback(
  slug: string,
  payload: { body: string; kind?: string; author?: string }
): Promise<AppFeedback> {
  return req<AppFeedback>('POST', `/apps/${encodeURIComponent(slug)}/feedback`, payload);
}

export async function refreshFeedback(feedbackId: string): Promise<AppFeedback> {
  return req<AppFeedback>('POST', `/feedback/${encodeURIComponent(feedbackId)}/refresh`);
}

export async function fetchBridges(): Promise<Bridge[]> {
  const data = await req<{ bridges: Bridge[] }>('GET', '/bridges');
  return data.bridges || [];
}
