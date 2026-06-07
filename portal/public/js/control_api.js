const TOKEN_KEY = "syoch_control_token";
const DEVICE_ID_KEY = "syoch_control_device_id";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token, deviceId) {
  localStorage.setItem(TOKEN_KEY, token);
  if (deviceId) localStorage.setItem(DEVICE_ID_KEY, deviceId);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(DEVICE_ID_KEY);
}

export function getDeviceId() {
  return localStorage.getItem(DEVICE_ID_KEY);
}

async function _req(method, path, body) {
  const token = getToken();
  const headers = { "Accept": "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch("/api/control" + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = await res.text(); }
    const err = new Error(detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function fetchMe() {
  return _req("GET", "/devices/me");
}

export async function fetchDevices() {
  const data = await _req("GET", "/devices");
  return data.devices || [];
}

export async function fetchAcl() {
  const data = await _req("GET", "/acls");
  return data.acls || [];
}

export async function createAcl(acl) {
  return _req("POST", "/acls", acl);
}

export async function updateAcl(aclId, patch) {
  return _req("PATCH", `/acls/${aclId}`, patch);
}

export async function deleteAcl(aclId) {
  return _req("DELETE", `/acls/${aclId}`);
}

export async function fetchOperations() {
  const data = await _req("GET", "/operations");
  return data.operations || [];
}

export async function fetchCommands(opts = {}) {
  const { status, from, to, op, limit, offset } = opts;
  const params = {};
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
  const data = await _req("GET", path);
  return {
    commands: data.commands || [],
    total: data.total || 0,
    limit: data.limit,
    offset: data.offset,
  };
}

export async function fetchCommand(id) {
  return _req("GET", `/commands/${id}`);
}

export async function issueCommand(body) {
  return _req("POST", "/commands", body);
}

export async function registerDevice({ device_id, display_name, bootstrap_token }) {
  const res = await fetch("/api/control/devices/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id, display_name, bootstrap_token }),
  });
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = await res.text(); }
    const err = new Error(detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function setAdmin(deviceId, isAdmin) {
  return _req("POST", `/devices/${deviceId}/set-admin`, { is_first_webui_device: isAdmin });
}

export async function patchDevice(deviceId, patch) {
  return _req("PATCH", `/devices/${deviceId}`, patch);
}

export async function deleteDevice(deviceId) {
  return _req("DELETE", `/devices/${deviceId}`);
}

let _sseSource = null;
let _sseHandlers = new Set();

export function subscribeSse(handler) {
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

function _startSse() {
  const token = getToken();
  if (!token) return;
  const url = `/api/control/events?token=${encodeURIComponent(token)}`;
  const es = new EventSource(url);
  es.addEventListener("command_status", (ev) => {
    try {
      const data = JSON.parse(ev.data);
      for (const h of _sseHandlers) h(data);
    } catch (e) {
      console.error("SSE parse error", e);
    }
  });
  es.onerror = (e) => {
    console.warn("SSE error", e);
  };
  _sseSource = es;
}

export function refreshSse() {
  if (_sseSource) {
    _sseSource.close();
    _sseSource = null;
  }
  if (_sseHandlers.size > 0) _startSse();
}
