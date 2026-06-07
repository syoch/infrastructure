import { fetchDevices, setAdmin, deleteDevice, subscribeSse, Device } from './control_api.js';
import { escapeHTML } from './ui.js';

let _sseUnsub: (() => void) | null = null;
let _me: Device | null = null;

export async function initDevicesSection(me: Device): Promise<void> {
  _me = me;
  const view = document.getElementById('control-view');
  if (!view) return;
  view.innerHTML = `
    <section class="control-section">
      <header class="control-section-header">
        <h2>Devices</h2>
        <span class="control-section-subtitle">${escapeHTML(_me?.id || '')} ${_me?.is_first_webui_device ? '(admin)' : ''}</span>
      </header>
      <div id="devices-list"></div>
    </section>
  `;
  await refresh();
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
    render(devices);
  } catch (e) {
    const el = document.getElementById('devices-list');
    if (el) el.innerHTML = `<p style="color: #ff5252;">Error: ${escapeHTML(e instanceof Error ? e.message : String(e))}</p>`;
  }
}

function render(devices: Device[]): void {
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