const TOKEN_KEY = 'syoch_control_token';
const DEVICE_ID_KEY = 'syoch_control_device_id';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string, deviceId?: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  if (deviceId) localStorage.setItem(DEVICE_ID_KEY, deviceId);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(DEVICE_ID_KEY);
}

export function getDeviceId(): string | null {
  return localStorage.getItem(DEVICE_ID_KEY);
}

interface RequestOptions {
  method: string;
  path: string;
  body?: unknown;
}

async function _req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch('/api/control' + path, {
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

export interface Device {
  id: string;
  display_name: string;
  bearer_token: string;
  created_at: string;
  last_seen: string | null;
  ws_state: 'online' | 'offline' | 'never_connected';
  is_first_webui_device: boolean;
  registered_operations: OperationSpec[];
}

export interface OperationSpec {
  id: string;
  name: string;
  group: string;
  description: string;
  command: string[];
  shell: boolean;
  timeout_seconds: number;
  ui_hint: UIHint;
  params_schema: object;
  is_builtin: boolean;
  provider: string;
}

export interface UIHint {
  kind: 'button' | 'form';
  label: string;
  timeout_seconds?: number;
}

export interface ACL {
  id: string;
  source_device: string;
  target_device: string;
  operation: string;
  extra: string;
  created_at: string;
}

export interface CommandRequest {
  id: string;
  source_device_id: string;
  target_device_id: string;
  operation_id: string;
  params: object;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result: object | null;
  error: string | null;
}

export interface CommandsResponse {
  commands: CommandRequest[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchMe(): Promise<Device> {
  return _req('GET', '/devices/me');
}

export async function fetchDevices(): Promise<Device[]> {
  const data = await _req<{ devices: Device[] }>('GET', '/devices');
  return data.devices || [];
}

export async function fetchAcl(): Promise<ACL[]> {
  const data = await _req<{ acls: ACL[] }>('GET', '/acls');
  return data.acls || [];
}

export async function createAcl(acl: { source_device: string; target_device: string; operation: string; extra?: string }): Promise<ACL> {
  return _req('POST', '/acls', acl);
}

export async function updateAcl(aclId: string, patch: Partial<ACL>): Promise<ACL> {
  return _req('PATCH', `/acls/${aclId}`, patch);
}

export async function deleteAcl(aclId: string): Promise<{ status: string }> {
  return _req('DELETE', `/acls/${aclId}`);
}

export async function fetchOperations(): Promise<OperationSpec[]> {
  const data = await _req<{ operations: OperationSpec[] }>('GET', '/operations');
  return data.operations || [];
}

export interface FetchCommandsOptions {
  status?: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  from?: string;
  to?: string;
  op?: string;
  limit?: number;
  offset?: number;
}

export async function fetchCommands(opts: FetchCommandsOptions = {}): Promise<CommandsResponse> {
  const { status, from, to, op, limit, offset } = opts;
  const params: Record<string, string> = {};
  if (status) params.status = status;
  if (from) params.from = from;
  if (to) params.to = to;
  if (op) params.op = op;
  if (limit !== undefined && limit !== null) params.limit = String(limit);
  if (offset !== undefined && offset !== null) params.offset = String(offset);
  const qs = Object.entries(params)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  const path = qs ? `/commands?${qs}` : '/commands';
  const data = await _req<CommandsResponse>('GET', path);
  return {
    commands: data.commands || [],
    total: data.total || 0,
    limit: data.limit,
    offset: data.offset,
  };
}

export async function fetchCommand(id: string): Promise<CommandRequest> {
  return _req('GET', `/commands/${id}`);
}

export async function issueCommand(body: {
  target_device_id: string;
  operation: string;
  params?: object;
}): Promise<CommandRequest> {
  return _req('POST', '/commands', body);
}

export async function registerDevice({
  device_id,
  display_name,
  bootstrap_token,
}: {
  device_id: string;
  display_name: string;
  bootstrap_token: string;
}): Promise<Device> {
  const res = await fetch('/api/control/devices/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_id, display_name, bootstrap_token }),
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
  return res.json();
}

export async function setAdmin(deviceId: string, isAdmin: boolean): Promise<Device> {
  return _req('POST', `/devices/${deviceId}/set-admin`, { is_first_webui_device: isAdmin });
}

export async function patchDevice(deviceId: string, patch: Partial<Device>): Promise<Device> {
  return _req('PATCH', `/devices/${deviceId}`, patch);
}

export async function deleteDevice(deviceId: string): Promise<{ status: string }> {
  return _req('DELETE', `/devices/${deviceId}`);
}

type SSEHandler = (data: unknown) => void;

let _sseSource: EventSource | null = null;
let _sseHandlers = new Set<SSEHandler>();

export function subscribeSse(handler: SSEHandler): () => void {
  _sseHandlers.add(handler);
  if (!_sseSource) _startSse();
  return () => {
    _sseHandlers.delete(handler);
    if (_sseHandlers.size === 0 && _sseSource) {
      _sseSource.close();
      _sseSource = null;
    }
  };
}

function _startSse(): void {
  const token = getToken();
  if (!token) return;
  const url = `/api/control/events?token=${encodeURIComponent(token)}`;
  const es = new EventSource(url);
  es.addEventListener('command_status', (ev: MessageEvent) => {
    try {
      const data = JSON.parse(ev.data);
      for (const h of _sseHandlers) h(data);
    } catch (e) {
      console.error('SSE parse error', e);
    }
  });
  es.onerror = (e: Event) => {
    console.warn('SSE error', e);
  };
  _sseSource = es;
}

export function refreshSse(): void {
  if (_sseSource) {
    _sseSource.close();
    _sseSource = null;
  }
  if (_sseHandlers.size > 0) _startSse();
}