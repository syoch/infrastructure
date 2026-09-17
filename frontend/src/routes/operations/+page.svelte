<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { Tabs } from '@skeletonlabs/skeleton-svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import {
    getToken,
    fetchDevices,
    fetchOperations,
    fetchCommands,
    subscribeSse,
    type Device,
    type OperationSpec,
    type CommandRequest,
  } from '../../api/control_api.js';
  import { ensureMe } from '../../lib/auth.svelte.ts';
  import { SchemaNode, type JSONSchema } from '../../lib/schema.svelte.ts';
  import CommandFilterForm from './CommandFilterForm.svelte';
  import OperationProviderCards from './OperationProviderCards.svelte';
  import CommandsTable from './CommandsTable.svelte';
  import CommandsPagination from './CommandsPagination.svelte';
  import OperationDialog from './OperationDialog.svelte';

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
  let modalNode = $state<SchemaNode | null>(null);
  let modalProvider = $state('');

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

  const routeParams = $derived<Record<string, string>>(
    Object.fromEntries(page.url.searchParams.entries())
  );

  $effect(() => {
    const currentParams = routeParams;
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

  const pageFrom = $derived(total === 0 ? 0 : applied.offset + 1);
  const pageTo = $derived(Math.min(applied.offset + applied.limit, total));
  const paginationPage = $derived(Math.floor(applied.offset / applied.limit) + 1);

  function openOpForm(op: OperationSpec, provider: string): void {
    modalOp = op;
    modalProvider = provider;
    const schema = (op.params_schema && Object.keys(op.params_schema).length > 0
      ? op.params_schema
      : { type: 'object', properties: {} }) as JSONSchema;
    modalNode = new SchemaNode(schema, schema);
  }

  function closeModal(): void {
    modalOp = null;
    modalNode = null;
    modalProvider = '';
  }

  function onOperationSubmitted(): void {
    closeModal();
    applied = { ...applied, offset: 0 };
    syncHash();
    void refreshAll();
    activeTab = 'cmds';
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

<div id="operations-view">
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
        <OperationProviderCards {ops} {onlineProviders} onOpen={openOpForm} />
      </Tabs.Content>

      <Tabs.Content value="cmds" id="cmds-pane" data-testid="cmds-pane">
        <CommandFilterForm
          bind:status={formStatus}
          bind:from={formFrom}
          bind:to={formTo}
          bind:op={formOp}
          bind:limit={formLimit}
          onApply={applyFilter}
          onReset={resetFilter}
        />
        <CommandsTable {cmds} />
        <CommandsPagination
          {total}
          limit={applied.limit}
          page={paginationPage}
          {pageFrom}
          {pageTo}
          onPageChange={onPageChange}
        />
      </Tabs.Content>
    </Tabs>
  </section>

  {#if modalOp && modalNode}
    <OperationDialog
      op={modalOp}
      node={modalNode}
      provider={modalProvider}
      onClose={closeModal}
      onSubmitted={onOperationSubmitted}
    />
  {/if}
</div>
