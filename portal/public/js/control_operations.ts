import {
  fetchMe,
  fetchDevices,
  fetchOperations,
  fetchCommands,
  issueCommand,
  subscribeSse,
  Device,
  OperationSpec,
  CommandRequest,
  CommandsResponse,
} from './control_api.js';
import { renderOpButton, renderOpForm, renderOperationStatus } from './control_op_renderer.js';
import { buildHash } from './router.js';
import { escapeHTML } from './ui.js';

interface Filter {
  status: string;
  from: string;
  to: string;
  op: string;
  limit: number;
  offset: number;
}

let _me: Device | null = null;
let _devices: Device[] = [];
let _ops: OperationSpec[] = [];
let _cmds: CommandsResponse = { commands: [], total: 0, limit: 25, offset: 0 };
let _filter: Filter = { status: '', from: '', to: '', op: '', limit: 25, offset: 0 };
let _sseUnsub: (() => void) | null = null;
let _autoRefreshTimer: ReturnType<typeof setInterval> | null = null;

export async function initOperationsSection(params: Record<string, string> = {}): Promise<void> {
  _me = await fetchMe();
  _filter = parseFilterFromParams(params);
  _sseUnsub = subscribeSse((data: unknown) => handleSseEvent(data as SseEvent));
  startAutoRefresh();
  await refreshAll();
}

export function teardownOperationsSection(): void {
  if (_sseUnsub) { _sseUnsub(); _sseUnsub = null; }
  if (_autoRefreshTimer) { clearInterval(_autoRefreshTimer); _autoRefreshTimer = null; }
  const view = document.getElementById('operations-view');
  if (view) view.innerHTML = '';
}

export function isOperationsActive(): boolean {
  return !!_sseUnsub;
}

function parseFilterFromParams(params: Record<string, string>): Filter {
  const limitRaw = parseInt(params.limit, 10);
  const offsetRaw = parseInt(params.offset, 10);
  return {
    status: params.status || '',
    from: params.from || '',
    to: params.to || '',
    op: params.op || '',
    limit: [10, 25, 50].includes(limitRaw) ? limitRaw : 25,
    offset: Number.isFinite(offsetRaw) && offsetRaw >= 0 ? offsetRaw : 0,
  };
}

function syncHash(): void {
  const params: Record<string, string | number | undefined> = {
    status: _filter.status || undefined,
    from: _filter.from || undefined,
    to: _filter.to || undefined,
    op: _filter.op || undefined,
    limit: _filter.limit === 25 ? undefined : _filter.limit,
    offset: _filter.offset > 0 ? _filter.offset : undefined,
  };
  const newHash = buildHash('operations', '', params);
  if (window.location.hash !== newHash) {
    window.location.replace(newHash);
  }
}

async function refreshAll(): Promise<void> {
  const [devices, ops, cmds] = await Promise.all([
    fetchDevices().catch((e: Error) => { console.error('devices', e); return [] as Device[]; }),
    fetchOperations().catch((e: Error) => { console.error('ops', e); return [] as OperationSpec[]; }),
    fetchCommands({
      status: (_filter.status || undefined) as 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled' | undefined,
      from: _filter.from || undefined,
      to: _filter.to || undefined,
      op: _filter.op || undefined,
      limit: _filter.limit,
      offset: _filter.offset,
    }).catch((e: Error) => {
      console.error('cmds', e);
      return { commands: [] as CommandRequest[], total: 0, limit: _filter.limit, offset: _filter.offset };
    }),
  ]);
  _devices = devices;
  _ops = ops;
  _cmds = cmds;
  render();
}

interface SseEvent {
  type: string;
  command_id?: string;
  status?: string;
  operation?: string;
  source_device_id?: string;
  target_device_id?: string;
  created_at?: string;
  completed_at?: string;
  result?: object | null;
  error?: string | null;
}

function handleSseEvent(ev: SseEvent): void {
  if (ev.type !== 'command_status') return;
  const idx = _cmds.commands.findIndex((c) => c.id === ev.command_id);
  if (idx >= 0) {
    _cmds.commands[idx] = { ..._cmds.commands[idx], ...ev } as CommandRequest;
  } else {
    if (_filter.offset === 0) {
      const minimal: CommandRequest = {
        id: ev.command_id || '',
        source_device_id: ev.source_device_id || '',
        target_device_id: ev.target_device_id || '',
        operation_id: ev.operation || '',
        params: {},
        status: (ev.status as CommandRequest['status']) || 'pending',
        created_at: ev.created_at || new Date().toISOString(),
        started_at: null,
        finished_at: ev.completed_at || null,
        result: ev.result || null,
        error: ev.error || null,
      };
      _cmds.commands = [minimal, ..._cmds.commands].slice(0, _filter.limit);
      _cmds.total = (_cmds.total || 0) + 1;
    }
  }
  render();
}

function startAutoRefresh(): void {
  if (_autoRefreshTimer) clearInterval(_autoRefreshTimer);
  _autoRefreshTimer = setInterval(refreshAll, 30000);
}

function render(): void {
  const view = document.getElementById('operations-view');
  if (!view) return;
  view.innerHTML = `
    <section class="control-section">
      <header class="control-section-header">
        <h2>Operations</h2>
        <span class="control-section-subtitle">${escapeHTML(_me?.id || '')}</span>
      </header>
      <div class="control-tabs" role="tablist">
        <button class="control-tab active" data-tab="ops" role="tab" aria-selected="true">Operations</button>
        <button class="control-tab" data-tab="cmds" role="tab" aria-selected="false">Commands</button>
      </div>
      <div id="ops-pane" class="control-tab-pane" role="tabpanel"></div>
      <div id="cmds-pane" class="control-tab-pane" role="tabpanel" style="display: none;"></div>
    </section>
  `;
  renderOps();
  renderCmds();

  view.querySelectorAll('.control-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      const which = (tab as HTMLElement).dataset.tab;
      view.querySelectorAll('.control-tab').forEach((t) => {
        const active = t === tab;
        t.classList.toggle('active', active);
        t.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      const opsPane = view.querySelector('#ops-pane') as HTMLElement;
      const cmdsPane = view.querySelector('#cmds-pane') as HTMLElement;
      opsPane.style.display = which === 'ops' ? '' : 'none';
      cmdsPane.style.display = which === 'cmds' ? '' : 'none';
    });
  });
}

function renderOps(): void {
  const el = document.getElementById('ops-pane');
  if (!el) return;
  el.innerHTML = '';
  if (!_ops.length) {
    el.innerHTML = `<p style="color: #888;">No operations available.</p>`;
    return;
  }
  const onlineProviders = new Set(
    _devices.filter((d) => d.ws_state === 'online').map((d) => `device:${d.id}`)
  );

  const byProvider = new Map<string, OperationSpec[]>();
  for (const op of _ops) {
    if (!byProvider.has(op.provider)) byProvider.set(op.provider, []);
    byProvider.get(op.provider)!.push(op);
  }

  for (const [provider, ops] of byProvider) {
    const card = document.createElement('div');
    card.className = 'provider-card';
    const isOnline = onlineProviders.has(provider);
    const statusColor = isOnline ? '#20a020' : '#888';
    card.innerHTML = `
      <div class="provider-card-header">
        ${escapeHTML(provider)}
        <span class="provider-status" style="color: ${statusColor};">${isOnline ? 'online' : 'offline'}</span>
      </div>
    `;
    const btnRow = document.createElement('div');
    btnRow.className = 'provider-card-buttons';
    for (const op of ops) {
      const btn = renderOpButton(op, (opArg) => openOpForm(opArg, provider));
      if (!isOnline) {
        btn.disabled = true;
        btn.title = 'Provider is offline';
      }
      btnRow.appendChild(btn);
    }
    card.appendChild(btnRow);
    el.appendChild(card);
  }
}

function openOpForm(op: OperationSpec, provider: string): void {
  const targetId = provider.replace(/^device:/, '');
  if (!_me) return;
  const me = _me;
    renderOpForm(op, me.id, targetId, async (body) => {
    await issueCommand({
      target_device_id: body.target_device_id,
      operation: body.operation,
      params: body.params,
    });
    _filter = { ..._filter, offset: 0 };
    syncHash();
    await refreshAll();
    const tabs = document.querySelectorAll('.control-tab');
    for (const t of tabs) {
      if ((t as HTMLElement).dataset.tab === 'cmds') { (t as HTMLElement).click(); break; }
    }
  });
}

function renderCmds(): void {
  const el = document.getElementById('cmds-pane');
  if (!el) return;
  el.innerHTML = '';

  const filterBar = document.createElement('div');
  filterBar.className = 'control-filter-bar';
  filterBar.innerHTML = `
    <label>Status
      <select id="cmds-filter-status">
        <option value="">all</option>
        <option value="pending">pending</option>
        <option value="claimed">claimed</option>
        <option value="succeeded">succeeded</option>
        <option value="failed">failed</option>
        <option value="timeout">timeout</option>
        <option value="cancelled">cancelled</option>
      </select>
    </label>
    <label>From
      <input type="datetime-local" id="cmds-filter-from">
    </label>
    <label>To
      <input type="datetime-local" id="cmds-filter-to">
    </label>
    <label>Op
      <input type="text" id="cmds-filter-op" placeholder="e.g. config">
    </label>
    <label>Page size
      <select id="cmds-filter-limit">
        <option value="10">10</option>
        <option value="25">25</option>
        <option value="50">50</option>
      </select>
    </label>
    <button class="btn btn-primary" id="cmds-filter-apply">適用</button>
    <button class="btn btn-secondary" id="cmds-filter-reset">リセット</button>
  `;
  el.appendChild(filterBar);

  (filterBar.querySelector('#cmds-filter-status') as HTMLSelectElement).value = _filter.status;
  (filterBar.querySelector('#cmds-filter-from') as HTMLInputElement).value = _filter.from;
  (filterBar.querySelector('#cmds-filter-to') as HTMLInputElement).value = _filter.to;
  (filterBar.querySelector('#cmds-filter-op') as HTMLInputElement).value = _filter.op;
  (filterBar.querySelector('#cmds-filter-limit') as HTMLSelectElement).value = String(_filter.limit);

  filterBar.querySelector('#cmds-filter-apply')!.addEventListener('click', () => {
    _filter = {
      status: (filterBar.querySelector('#cmds-filter-status') as HTMLSelectElement).value,
      from: (filterBar.querySelector('#cmds-filter-from') as HTMLInputElement).value,
      to: (filterBar.querySelector('#cmds-filter-to') as HTMLInputElement).value,
      op: (filterBar.querySelector('#cmds-filter-op') as HTMLInputElement).value,
      limit: parseInt((filterBar.querySelector('#cmds-filter-limit') as HTMLSelectElement).value, 10) || 25,
      offset: 0,
    };
    syncHash();
    refreshAll();
  });
  filterBar.querySelector('#cmds-filter-reset')!.addEventListener('click', () => {
    _filter = { status: '', from: '', to: '', op: '', limit: 25, offset: 0 };
    syncHash();
    refreshAll();
  });

  const table = document.createElement('table');
  table.className = 'control-table';
  table.innerHTML = `
    <thead><tr>
      <th>ID</th><th>Op</th><th>Source</th><th>Target</th>
      <th>Status</th><th>Created</th><th>Completed</th><th>Result</th>
    </tr></thead><tbody></tbody>
  `;
  const tbody = table.querySelector('tbody');
  if (!tbody) return;
  if (!_cmds.commands.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="color: #888;">No commands yet.</td></tr>`;
  } else {
    for (const c of _cmds.commands) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code class="mono">${escapeHTML(c.id.substring(0, 8))}</code></td>
        <td>${escapeHTML(c.operation_id)}</td>
        <td>${escapeHTML(c.source_device_id)}</td>
        <td>${escapeHTML(c.target_device_id)}</td>
        <td>${renderOperationStatus(c)}</td>
        <td>${escapeHTML((c.created_at || '').toString().substring(0, 19))}</td>
        <td>${escapeHTML((c.finished_at || '').toString().substring(0, 19))}</td>
        <td><code class="mono">${escapeHTML(JSON.stringify(c.result || c.error || '').substring(0, 60))}</code></td>
      `;
      tbody.appendChild(tr);
    }
  }
  el.appendChild(table);

  const pagination = document.createElement('div');
  pagination.className = 'control-pagination';
  const total = _cmds.total || 0;
  const from = total === 0 ? 0 : _cmds.offset + 1;
  const to = Math.min(_cmds.offset + _cmds.limit, total);
  pagination.innerHTML = `
    <span class="control-pagination-info">Showing ${from}-${to} of ${total}</span>
    <button class="btn btn-secondary" id="cmds-page-prev" ${_cmds.offset === 0 ? 'disabled' : ''}>前へ</button>
    <button class="btn btn-secondary" id="cmds-page-next" ${to >= total ? 'disabled' : ''}>次へ</button>
  `;
  el.appendChild(pagination);
  pagination.querySelector('#cmds-page-prev')!.addEventListener('click', () => {
    if (_cmds.offset === 0) return;
    _filter = { ..._filter, offset: Math.max(0, _cmds.offset - _filter.limit) };
    syncHash();
    refreshAll();
  });
  pagination.querySelector('#cmds-page-next')!.addEventListener('click', () => {
    if (to >= total) return;
    _filter = { ..._filter, offset: _cmds.offset + _filter.limit };
    syncHash();
    refreshAll();
  });
}

export function applyOperationsFilterFromHash(params: Record<string, string>): boolean {
  if (!_sseUnsub) return false;
  const newFilter = parseFilterFromParams(params);
  const changed = JSON.stringify(newFilter) !== JSON.stringify(_filter);
  if (changed) {
    _filter = newFilter;
    refreshAll();
  }
  return changed;
}