<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import {
    getToken,
    fetchDevices,
    fetchOperations,
    fetchCommands,
    issueCommand,
    subscribeSse,
    type Device,
    type OperationSpec,
    type CommandRequest,
  } from '../api/control_api.js';
  import { ensureMe } from '../lib/auth.svelte.ts';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { SchemaNode, type JSONSchema } from '../lib/schema.svelte.ts';
  import SchemaForm from '../components/SchemaForm.svelte';

  let { params = {} }: { params?: Record<string, string> } = $props();

  interface Filter {
    status: string;
    from: string;
    to: string;
    op: string;
    limit: number;
    offset: number;
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

  let me = $state<Device | null>(null);
  let devices = $state<Device[]>([]);
  let ops = $state<OperationSpec[]>([]);
  let cmds = $state<CommandRequest[]>([]);
  let total = $state(0);
  let applied = $state<Filter>({ status: '', from: '', to: '', op: '', limit: 25, offset: 0 });
  let activeTab = $state<'ops' | 'cmds'>('ops');

  let formStatus = $state('');
  let formFrom = $state('');
  let formTo = $state('');
  let formOp = $state('');
  let formLimit = $state(25);

  let modalOp = $state<OperationSpec | null>(null);
  let modalProvider = $state('');
  let modalNode = $state<SchemaNode | null>(null);
  let modalError = $state('');
  let modalBusy = $state(false);

  let initialized = false;

  function msg(e: unknown): string {
    return e instanceof Error ? e.message : String(e);
  }

  function parseFilter(p: Record<string, string>): Filter {
    const limitRaw = parseInt(p.limit ?? '', 10);
    const offsetRaw = parseInt(p.offset ?? '', 10);
    return {
      status: p.status || '',
      from: p.from || '',
      to: p.to || '',
      op: p.op || '',
      limit: [10, 25, 50].includes(limitRaw) ? limitRaw : 25,
      offset: Number.isFinite(offsetRaw) && offsetRaw >= 0 ? offsetRaw : 0,
    };
  }

  function sameFilter(a: Filter, b: Filter): boolean {
    return (
      a.status === b.status &&
      a.from === b.from &&
      a.to === b.to &&
      a.op === b.op &&
      a.limit === b.limit &&
      a.offset === b.offset
    );
  }

  function syncFormFromApplied(): void {
    formStatus = applied.status;
    formFrom = applied.from;
    formTo = applied.to;
    formOp = applied.op;
    formLimit = applied.limit;
  }

  function syncHash(): void {
    const search = new URLSearchParams();
    if (applied.status) search.set('status', applied.status);
    if (applied.from) search.set('from', applied.from);
    if (applied.to) search.set('to', applied.to);
    if (applied.op) search.set('op', applied.op);
    if (applied.limit !== 25) search.set('limit', String(applied.limit));
    if (applied.offset > 0) search.set('offset', String(applied.offset));
    const qs = search.toString();
    const target = qs ? `/operations?${qs}` : '/operations';
    if (`${page.url.pathname}${page.url.search}` !== target) {
      void goto(target, { replaceState: true, noScroll: true, keepFocus: true });
    }
  }

  $effect(() => {
    const currentParams = params;
    untrack(() => {
      void routeChanged(currentParams);
    });
  });

  async function routeChanged(currentParams: Record<string, string>): Promise<void> {
    if (!getToken()) {
      void goto('/control/devices');
      return;
    }
    if (!initialized) {
      initialized = true;
      me = await ensureMe();
      applied = parseFilter(currentParams);
      syncFormFromApplied();
      await refreshAll();
      return;
    }
    const next = parseFilter(currentParams);
    if (!sameFilter(next, applied)) {
      applied = next;
      syncFormFromApplied();
      await refreshAll();
    }
  }

  onMount(() => {
    const unsubscribe = subscribeSse((data) => handleSse(data as SseEvent));
    const timer = setInterval(() => {
      void refreshAll();
    }, 30000);
    return () => {
      unsubscribe();
      clearInterval(timer);
    };
  });

  async function refreshAll(): Promise<void> {
    const [nextDevices, nextOps, nextCmds] = await Promise.all([
      fetchDevices().catch((e) => {
        console.error('devices', e);
        return [] as Device[];
      }),
      fetchOperations().catch((e) => {
        console.error('ops', e);
        return [] as OperationSpec[];
      }),
      fetchCommands({
        status: (applied.status || undefined) as
          | 'pending'
          | 'running'
          | 'succeeded'
          | 'failed'
          | 'cancelled'
          | undefined,
        from: applied.from || undefined,
        to: applied.to || undefined,
        op: applied.op || undefined,
        limit: applied.limit,
        offset: applied.offset,
      }).catch((e) => {
        console.error('cmds', e);
        return { commands: [] as CommandRequest[], total: 0, limit: applied.limit, offset: applied.offset };
      }),
    ]);
    devices = nextDevices;
    ops = nextOps;
    cmds = nextCmds.commands;
    total = nextCmds.total;
  }

  function handleSse(ev: SseEvent): void {
    if (ev.type !== 'command_status') return;
    const index = cmds.findIndex((c) => c.id === ev.command_id);
    if (index >= 0) {
      const next = [...cmds];
      next[index] = { ...next[index], ...ev } as CommandRequest;
      cmds = next;
    } else if (applied.offset === 0) {
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
      cmds = [minimal, ...cmds].slice(0, applied.limit);
      total = total + 1;
    }
  }

  const onlineProviders = $derived(
    new Set(devices.filter((d) => d.ws_state === 'online').map((d) => `device:${d.id}`))
  );

  const providerEntries = $derived.by(() => {
    const map = new Map<string, OperationSpec[]>();
    for (const op of ops) {
      const list = map.get(op.provider);
      if (list) list.push(op);
      else map.set(op.provider, [op]);
    }
    return [...map.entries()];
  });

  const pageFrom = $derived(total === 0 ? 0 : applied.offset + 1);
  const pageTo = $derived(Math.min(applied.offset + applied.limit, total));

  function statusColor(status: string): string {
    const colors: Record<string, string> = {
      pending: '#f0a020',
      claimed: '#2080f0',
      succeeded: '#20a020',
      failed: '#ff5252',
      timeout: '#888',
      cancelled: '#888',
    };
    return colors[status] || '#888';
  }

  function openOpForm(op: OperationSpec, provider: string): void {
    modalOp = op;
    modalProvider = provider;
    modalError = '';
    modalBusy = false;
    const schema = (op.params_schema && Object.keys(op.params_schema).length > 0
      ? op.params_schema
      : { type: 'object', properties: {} }) as JSONSchema;
    modalNode = new SchemaNode(schema, schema);
  }

  function closeModal(): void {
    modalOp = null;
    modalNode = null;
    modalError = '';
    modalBusy = false;
  }

  async function onModalSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    if (!modalOp || !modalNode) return;
    let commandParams: object;
    try {
      commandParams = (modalNode.getValue() as object) || {};
    } catch (err) {
      modalError = msg(err);
      return;
    }
    modalBusy = true;
    modalError = '';
    const targetId = modalProvider.replace(/^device:/, '');
    try {
      await issueCommand({
        target_device_id: targetId,
        operation: modalOp.id,
        params: commandParams,
      });
      closeModal();
      applied = { ...applied, offset: 0 };
      syncHash();
      await refreshAll();
      activeTab = 'cmds';
    } catch (err) {
      modalError = msg(err);
      modalBusy = false;
    }
  }

  function applyFilter(): void {
    applied = {
      status: formStatus,
      from: formFrom,
      to: formTo,
      op: formOp,
      limit: formLimit,
      offset: 0,
    };
    syncHash();
    void refreshAll();
  }

  function resetFilter(): void {
    formStatus = '';
    formFrom = '';
    formTo = '';
    formOp = '';
    formLimit = 25;
    applied = { status: '', from: '', to: '', op: '', limit: 25, offset: 0 };
    syncHash();
    void refreshAll();
  }

  function previousPage(): void {
    if (applied.offset === 0) return;
    applied = { ...applied, offset: Math.max(0, applied.offset - applied.limit) };
    syncHash();
    void refreshAll();
  }

  function nextPage(): void {
    if (pageTo >= total) return;
    applied = { ...applied, offset: applied.offset + applied.limit };
    syncHash();
    void refreshAll();
  }
</script>

<section class="control-section">
  <header class="control-section-header">
    <h2>Operations</h2>
    <span class="control-section-subtitle">{me?.id || ''}</span>
  </header>

  <div class="control-tabs" role="tablist">
    <button
      type="button"
      class="control-tab"
      class:active={activeTab === 'ops'}
      role="tab"
      aria-selected={activeTab === 'ops'}
      onclick={() => (activeTab = 'ops')}
    >
      Operations
    </button>
    <button
      type="button"
      class="control-tab"
      class:active={activeTab === 'cmds'}
      role="tab"
      aria-selected={activeTab === 'cmds'}
      onclick={() => (activeTab = 'cmds')}
    >
      Commands
    </button>
  </div>

  <div id="ops-pane" class="control-tab-pane" role="tabpanel" style={activeTab === 'ops' ? '' : 'display: none;'}>
    {#if ops.length === 0}
      <p style="color: #888;">No operations available.</p>
    {:else}
      {#each providerEntries as [provider, providerOps] (provider)}
        {@const isOnline = onlineProviders.has(provider)}
        <div class="provider-card">
          <div class="provider-card-header">
            {provider}
            <span class="provider-status" style="color: {isOnline ? '#20a020' : '#888'};">
              {isOnline ? 'online' : 'offline'}
            </span>
          </div>
          <div class="provider-card-buttons">
            {#each providerOps as op (op.id)}
              <button
                type="button"
                class="btn btn-primary"
                title={op.description || op.name}
                disabled={!isOnline}
                onclick={() => openOpForm(op, provider)}
              >
                {op.ui_hint?.label || op.name}
              </button>
            {/each}
          </div>
        </div>
      {/each}
    {/if}
  </div>

  <div id="cmds-pane" class="control-tab-pane" role="tabpanel" style={activeTab === 'cmds' ? '' : 'display: none;'}>
    <div class="control-filter-bar">
      <label for="cmds-filter-status">
        Status
        <select id="cmds-filter-status" bind:value={formStatus}>
          <option value="">all</option>
          <option value="pending">pending</option>
          <option value="claimed">claimed</option>
          <option value="succeeded">succeeded</option>
          <option value="failed">failed</option>
          <option value="timeout">timeout</option>
          <option value="cancelled">cancelled</option>
        </select>
      </label>
      <label for="cmds-filter-from">
        From
        <input type="datetime-local" id="cmds-filter-from" bind:value={formFrom} />
      </label>
      <label for="cmds-filter-to">
        To
        <input type="datetime-local" id="cmds-filter-to" bind:value={formTo} />
      </label>
      <label for="cmds-filter-op">
        Op
        <input type="text" id="cmds-filter-op" placeholder="e.g. config" bind:value={formOp} />
      </label>
      <label for="cmds-filter-limit">
        Page size
        <select id="cmds-filter-limit" bind:value={formLimit}>
          <option value={10}>10</option>
          <option value={25}>25</option>
          <option value={50}>50</option>
        </select>
      </label>
      <button type="button" class="btn btn-primary" id="cmds-filter-apply" onclick={applyFilter}>
        適用
      </button>
      <button type="button" class="btn btn-secondary" id="cmds-filter-reset" onclick={resetFilter}>
        リセット
      </button>
    </div>

    <table class="control-table">
      <thead>
        <tr>
          <th>ID</th><th>Op</th><th>Source</th><th>Target</th>
          <th>Status</th><th>Created</th><th>Completed</th><th>Result</th>
        </tr>
      </thead>
      <tbody>
        {#if cmds.length === 0}
          <tr><td colspan="8" style="color: #888;">No commands yet.</td></tr>
        {:else}
          {#each cmds as command (command.id)}
            <tr>
              <td><code class="mono">{command.id.substring(0, 8)}</code></td>
              <td>{command.operation_id}</td>
              <td>{command.source_device_id}</td>
              <td>{command.target_device_id}</td>
              <td>
                <span style="color: {statusColor(command.status)}; font-weight: 600;">
                  {command.status}
                </span>
              </td>
              <td>{(command.created_at || '').toString().substring(0, 19)}</td>
              <td>{(command.finished_at || '').toString().substring(0, 19)}</td>
              <td>
                <code class="mono">
                  {JSON.stringify(command.result || command.error || '').substring(0, 60)}
                </code>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>

    <div class="control-pagination">
      <span class="control-pagination-info">Showing {pageFrom}-{pageTo} of {total}</span>
      <button
        type="button"
        class="btn btn-secondary"
        id="cmds-page-prev"
        disabled={applied.offset === 0}
        onclick={previousPage}
      >
        前へ
      </button>
      <button
        type="button"
        class="btn btn-secondary"
        id="cmds-page-next"
        disabled={pageTo >= total}
        onclick={nextPage}
      >
        次へ
      </button>
    </div>
  </div>
</section>

{#if modalOp && modalNode}
  <div class="modal-backdrop active" style="display: flex;">
    <div class="modal-content" style="max-width: 560px;">
      <h2>{modalOp.ui_hint?.label || modalOp.name}</h2>
      <p style="color: var(--text-secondary, #888);">
        {modalOp.description || `Operation: ${modalOp.name}`}
      </p>
      <form
        style="display: flex; flex-direction: column; gap: 12px;"
        onsubmit={onModalSubmit}
      >
        <div class="schema-form-body">
          <SchemaForm node={modalNode} />
        </div>
        {#if modalError}
          <div style="color: #ff5252; font-size: 0.9em;">Error: {modalError}</div>
        {/if}
        <div class="form-actions" style="margin-top: 16px; display: flex; gap: 8px;">
          <button
            type="submit"
            class="btn btn-primary"
            disabled={modalBusy}
            style="flex: 2;"
          >
            {modalBusy ? '送信中…' : '実行'}
          </button>
          <button type="button" class="btn btn-secondary" style="flex: 1;" onclick={closeModal}>
            キャンセル
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
