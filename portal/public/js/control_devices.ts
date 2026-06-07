import {
  fetchDevices,
  setAdmin,
  deleteDevice,
  subscribeSse,
  fetchTokens,
  issueToken,
  deleteToken,
  Device,
  BootstrapToken,
} from './control_api.js';
import { escapeHTML } from './ui.js';

let _sseUnsub: (() => void) | null = null;
let _me: Device | null = null;

export async function initDevicesSection(me: Device): Promise<void> {
  _me = me;
  const view = document.getElementById('control-view');
  if (!view) return;
  const isAdmin = _me?.is_first_webui_device === true;
  view.innerHTML = `
    <section class="control-section">
      <header class="control-section-header">
        <h2>Devices</h2>
        <span class="control-section-subtitle">${escapeHTML(_me?.id || '')} ${_me?.is_first_webui_device ? '(admin)' : ''}</span>
      </header>
      <div id="devices-list"></div>
    </section>

    ${
      isAdmin
        ? `
    <section class="control-section" style="margin-top: 40px;">
      <header class="control-section-header">
        <h2>Bootstrap Tokens</h2>
        <button class="btn btn-primary" id="issue-token-btn">Issue Token</button>
      </header>
      <div id="tokens-list"></div>
    </section>
    `
        : ''
    }
  `;
  await refresh();
  if (isAdmin) {
    const issueBtn = document.getElementById('issue-token-btn');
    if (issueBtn) issueBtn.addEventListener('click', handleIssueToken);
  }
  if (!_sseUnsub) _sseUnsub = subscribeSse(() => { /* Devices は SSE 影響なし */ });
}

export function teardownDevicesSection(): void {
  if (_sseUnsub) { _sseUnsub(); _sseUnsub = null; }
  const view = document.getElementById('control-view');
  if (view) view.innerHTML = '';
}

async function refresh(): Promise<void> {
  try {
    const devices = await fetchDevices();
    renderDevices(devices);
  } catch (e) {
    const el = document.getElementById('devices-list');
    if (el) el.innerHTML = `<p style="color: #ff5252;">Error: ${escapeHTML(e instanceof Error ? e.message : String(e))}</p>`;
  }
  if (_me?.is_first_webui_device) {
    await refreshTokens();
  }
}

async function refreshTokens(): Promise<void> {
  try {
    const tokens = await fetchTokens();
    renderTokens(tokens);
  } catch (e) {
    const el = document.getElementById('tokens-list');
    if (el) el.innerHTML = `<p style="color: #ff5252;">Error: ${escapeHTML(e instanceof Error ? e.message : String(e))}</p>`;
  }
}

function renderDevices(devices: Device[]): void {
  const el = document.getElementById('devices-list');
  if (!el) return;
  el.innerHTML = '';
  if (!devices.length) {
    el.innerHTML = `<p style="color: #888;">No devices registered.</p>`;
    return;
  }
  const isAdmin = _me?.is_first_webui_device === true;
  const table = document.createElement('table');
  table.className = 'control-table';
  table.innerHTML = `
    <thead><tr>
      <th>ID</th><th>Display</th><th>WS</th><th>Last seen</th>
      ${isAdmin ? '<th>Admin</th><th></th>' : ''}
    </tr></thead><tbody></tbody>
  `;
  const tbody = table.querySelector('tbody');
  if (!tbody) return;
  for (const d of devices) {
    const tr = document.createElement('tr');
    const wsColor = d.ws_state === 'online' ? '#20a020' : d.ws_state === 'offline' ? '#888' : '#f0a020';
    tr.innerHTML = `
      <td><code>${escapeHTML(d.id)}</code></td>
      <td>${escapeHTML(d.display_name || '')}</td>
      <td><span style="color: ${wsColor};">${escapeHTML(d.ws_state || 'never_connected')}</span></td>
      <td>${escapeHTML((d.last_seen || '—').toString().replace('T', ' ').substring(0, 19))}</td>
      ${isAdmin ? `
        <td><input type="checkbox" data-device="${escapeHTML(d.id)}" data-action="admin" ${d.is_first_webui_device ? 'checked' : ''}></td>
        <td><button class="btn btn-secondary" data-device="${escapeHTML(d.id)}" data-action="delete" style="color: #ff5252;">Delete</button></td>
      ` : ''}
    `;
    tbody.appendChild(tr);
  }
  if (isAdmin) {
    tbody.addEventListener('change', async (e: Event) => {
      const target = e.target as HTMLInputElement;
      if (target.dataset.action === 'admin') {
        const id = target.dataset.device!;
        const value = target.checked;
        if (!confirm(value ? `${id} を admin に昇格しますか?` : `${id} から admin を剥奪しますか?`)) {
          target.checked = !value;
          return;
        }
        try {
          await setAdmin(id, value);
          await refresh();
        } catch (err) {
          alert(err instanceof Error ? err.message : String(err));
          target.checked = !value;
        }
      }
    });
    tbody.addEventListener('click', async (e: Event) => {
      const target = e.target as HTMLButtonElement;
      if (target.dataset.action === 'delete') {
        const id = target.dataset.device!;
        if (!confirm(`Device ${id} を削除しますか?`)) return;
        try {
          await deleteDevice(id);
          await refresh();
        } catch (err) {
          alert(err instanceof Error ? err.message : String(err));
        }
      }
    });
  }
  el.appendChild(table);
}

function renderTokens(tokens: BootstrapToken[]): void {
  const el = document.getElementById('tokens-list');
  if (!el) return;
  el.innerHTML = '';
  if (!tokens.length) {
    el.innerHTML = `<p style="color: #888;">No bootstrap tokens issued.</p>`;
    return;
  }
  const table = document.createElement('table');
  table.className = 'control-table';
  table.innerHTML = `
    <thead><tr>
      <th>Token</th><th>Target Device</th><th>Expires</th><th>Status</th><th></th>
    </tr></thead><tbody></tbody>
  `;
  const tbody = table.querySelector('tbody')!;
  const now = new Date();

  for (const t of tokens) {
    const tr = document.createElement('tr');
    const expires = new Date(t.expires_at);
    const isExpired = expires < now;
    const isConsumed = !!t.consumed_at;

    let statusHtml = '';
    if (isConsumed) {
      statusHtml = `<span style="color: #888;">Consumed</span>`;
    } else if (isExpired) {
      statusHtml = `<span style="color: #ff5252;">Expired</span>`;
    } else {
      statusHtml = `<span style="color: #20a020;">Pending</span>`;
    }

    const maskedToken = t.id.substring(0, 8) + '...';

    tr.innerHTML = `
      <td><code>${escapeHTML(maskedToken)}</code></td>
      <td>
        <div style="font-weight: 500;">${escapeHTML(t.device_id)}</div>
        <div style="font-size: 0.8em; color: #888;">${escapeHTML(t.display_name)}</div>
      </td>
      <td>${escapeHTML(t.expires_at.replace('T', ' ').substring(0, 19))}</td>
      <td>${statusHtml}</td>
      <td><button class="btn btn-secondary" data-token-id="${escapeHTML(t.id)}" data-action="revoke-token" style="color: #ff5252;">Revoke</button></td>
    `;
    tbody.appendChild(tr);
  }

  tbody.addEventListener('click', async (e: Event) => {
    const target = e.target as HTMLButtonElement;
    if (target.dataset.action === 'revoke-token') {
      const id = target.dataset.tokenId!;
      if (!confirm(`Bootstrap Token ${id.substring(0, 8)}... を失効させますか?`)) return;
      try {
        await deleteToken(id);
        await refreshTokens();
      } catch (err) {
        alert(err instanceof Error ? err.message : String(err));
      }
    }
  });

  el.appendChild(table);
}

async function handleIssueToken(): Promise<void> {
  const device_id = prompt('Target Device ID (e.g. tablet-01):');
  if (!device_id) return;
  const display_name = prompt('Display Name (e.g. My Android Tablet):');
  if (!display_name) return;
  const ttl_str = prompt('TTL in minutes (default 15):', '15');
  const ttl_minutes = ttl_str ? parseInt(ttl_str, 10) : 15;

  try {
    const res = await issueToken({ device_id, display_name, ttl_minutes });
    const msg = `Token issued successfully!\n\nID: ${res.id}\n\nNOTE: This token will not be shown again. Copy it now.`;
    alert(msg);
    await refreshTokens();
  } catch (err) {
    alert(err instanceof Error ? err.message : String(err));
  }
}
