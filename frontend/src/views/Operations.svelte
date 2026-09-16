<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { Dialog, Pagination, Portal, Tabs } from '@skeletonlabs/skeleton-svelte';
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
  const paginationPage = $derived(Math.floor(applied.offset / applied.limit) + 1);
  const modalTitle = $derived(modalOp ? modalOp.ui_hint?.label || modalOp.name : '');
  const modalDescription = $derived(
    modalOp ? modalOp.description || `Operation: ${modalOp.name}` : ''
  );

  function statusBadge(status: string): string {
    const cls: Record<string, string> = {
      pending: 'badge preset-filled-warning-500',
      claimed: 'badge preset-filled-primary-500',
      running: 'badge preset-filled-primary-500',
      succeeded: 'badge preset-filled-success-500',
      failed: 'badge preset-filled-error-500',
      timeout: 'badge preset-tonal-surface',
      cancelled: 'badge preset-tonal-surface',
    };
    return cls[status] || 'badge preset-tonal-surface';
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

  function onPageChange(details: { page: number }): void {
    const offset = Math.max(0, (details.page - 1) * applied.limit);
    if (offset === applied.offset) return;
    applied = { ...applied, offset };
    syncHash();
    void refreshAll();
  }
</script>

<section class="card bg-surface-100-900 mb-6 space-y-4 p-6">
  <header class="mb-4 flex flex-wrap items-center justify-between gap-2">
    <h2 class="h2">Operations</h2>
    <span class="font-mono text-sm text-surface-600-400">{me?.id || ''}</span>
  </header>

  <Tabs
    value={activeTab}
    onValueChange={(details) => {
      if (details.value === 'ops' || details.value === 'cmds') activeTab = details.value;
    }}
    data-testid="operations-tabs"
  >
    <Tabs.List>
      <Tabs.Trigger value="ops" data-testid="tab-ops">Operations</Tabs.Trigger>
      <Tabs.Trigger value="cmds" data-testid="tab-cmds">Commands</Tabs.Trigger>
      <Tabs.Indicator />
    </Tabs.List>

    <Tabs.Content value="ops" id="ops-pane" data-testid="ops-pane">
      {#if ops.length === 0}
        <p class="text-surface-600-400">No operations available.</p>
      {:else}
        {#each providerEntries as [provider, providerOps] (provider)}
          {@const isOnline = onlineProviders.has(provider)}
          <div data-testid="provider-card" class="card bg-surface-100-900 mb-4 p-4">
            <div class="mb-3 flex items-center gap-2 text-base font-semibold">
              {provider}
              <span
                class={isOnline ? 'badge preset-filled-success-500' : 'badge preset-tonal-surface'}
              >
                {isOnline ? 'online' : 'offline'}
              </span>
            </div>
            <div class="flex flex-wrap gap-2">
              {#each providerOps as op (op.id)}
                <button
                  type="button"
                  class="btn preset-filled-primary-500"
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
    </Tabs.Content>

    <Tabs.Content value="cmds" id="cmds-pane" data-testid="cmds-pane">
      <div class="card bg-surface-100-900 mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <label class="label" for="cmds-filter-status">
          <span class="label-text">Status</span>
          <select id="cmds-filter-status" class="select" bind:value={formStatus}>
            <option value="">all</option>
            <option value="pending">pending</option>
            <option value="claimed">claimed</option>
            <option value="succeeded">succeeded</option>
            <option value="failed">failed</option>
            <option value="timeout">timeout</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
        <label class="label" for="cmds-filter-from">
          <span class="label-text">From</span>
          <input type="datetime-local" id="cmds-filter-from" class="input" bind:value={formFrom} />
        </label>
        <label class="label" for="cmds-filter-to">
          <span class="label-text">To</span>
          <input type="datetime-local" id="cmds-filter-to" class="input" bind:value={formTo} />
        </label>
        <label class="label" for="cmds-filter-op">
          <span class="label-text">Op</span>
          <input type="text" id="cmds-filter-op" class="input" placeholder="e.g. config" bind:value={formOp} />
        </label>
        <label class="label" for="cmds-filter-limit">
          <span class="label-text">Page size</span>
          <select id="cmds-filter-limit" class="select" bind:value={formLimit}>
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
          </select>
        </label>
        <div class="flex items-end gap-2">
          <button type="button" class="btn preset-filled-primary-500" id="cmds-filter-apply" onclick={applyFilter}>
            適用
          </button>
          <button type="button" class="btn preset-tonal" id="cmds-filter-reset" onclick={resetFilter}>
            リセット
          </button>
        </div>
      </div>

      <div class="table-wrap card bg-surface-100-900 overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th><th>Op</th><th>Source</th><th>Target</th>
              <th>Status</th><th>Created</th><th>Completed</th><th>Result</th>
            </tr>
          </thead>
          <tbody>
            {#if cmds.length === 0}
              <tr><td colspan="8" class="text-surface-600-400">No commands yet.</td></tr>
            {:else}
              {#each cmds as command (command.id)}
                <tr>
                  <td><code class="font-mono">{command.id.substring(0, 8)}</code></td>
                  <td>{command.operation_id}</td>
                  <td>{command.source_device_id}</td>
                  <td>{command.target_device_id}</td>
                  <td>
                    <span class={statusBadge(command.status)}>
                      {command.status}
                    </span>
                  </td>
                  <td>{(command.created_at || '').toString().substring(0, 19)}</td>
                  <td>{(command.finished_at || '').toString().substring(0, 19)}</td>
                  <td>
                    <code class="font-mono">
                      {JSON.stringify(command.result || command.error || '').substring(0, 60)}
                    </code>
                  </td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-4">
        <span class="text-sm text-surface-600-400">Showing {pageFrom}-{pageTo} of {total}</span>
        <Pagination
          count={total}
          pageSize={applied.limit}
          page={paginationPage}
          onPageChange={(details) => onPageChange(details)}
        >
          <Pagination.PrevTrigger id="cmds-page-prev">前へ</Pagination.PrevTrigger>
          <Pagination.NextTrigger id="cmds-page-next">次へ</Pagination.NextTrigger>
        </Pagination>
      </div>
    </Tabs.Content>
  </Tabs>
</section>

{#if modalOp && modalNode}
  <Dialog
    open={true}
    aria-label={modalTitle}
    onOpenChange={(details) => {
      if (!details.open) closeModal();
    }}
  >
    <Portal>
      <Dialog.Backdrop class="fixed inset-0 z-[80] bg-surface-950/60" />
      <Dialog.Positioner class="fixed inset-0 z-[90] flex items-center justify-center p-4">
        <Dialog.Content
          id="op-modal"
          data-testid="op-modal"
          class="card bg-surface-100-900 relative max-h-[90vh] w-full max-w-xl overflow-y-auto p-6 shadow-xl"
        >
          <Dialog.Title>
            {#snippet element(attributes)}
              <h2 {...attributes} id="op-modal-title" class="mb-3 text-xl font-bold">
                {modalTitle}
              </h2>
            {/snippet}
          </Dialog.Title>
          <p class="mb-4 text-sm text-surface-600-400">
            {modalDescription}
          </p>
          <form id="op-form" class="flex flex-col gap-3" onsubmit={onModalSubmit}>
            <div class="schema-form-body">
              <SchemaForm node={modalNode} />
            </div>
            {#if modalError}
              <div class="text-sm text-error-500">Error: {modalError}</div>
            {/if}
            <div class="mt-6 flex gap-2">
              <button type="submit" class="btn preset-filled-primary-500 flex-[2]" disabled={modalBusy}>
                {modalBusy ? '送信中…' : '実行'}
              </button>
              <button type="button" class="btn preset-tonal flex-1" onclick={closeModal}>
                キャンセル
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Positioner>
    </Portal>
  </Dialog>
{/if}
