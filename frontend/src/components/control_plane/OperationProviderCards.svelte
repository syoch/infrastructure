<script lang="ts">
  import type { OperationSpec } from '../../api/control_api.js';

  let {
    ops,
    onlineProviders,
    onOpen,
  }: {
    ops: OperationSpec[];
    onlineProviders: Set<string>;
    onOpen: (op: OperationSpec, provider: string) => void;
  } = $props();

  const providerEntries = $derived.by(() => {
    const map = new Map<string, OperationSpec[]>();
    for (const op of ops) {
      const list = map.get(op.provider);
      if (list) list.push(op);
      else map.set(op.provider, [op]);
    }
    return [...map.entries()];
  });
</script>

{#if ops.length === 0}
  <p class="text-surface-600-400">No operations available.</p>
{:else}
  {#each providerEntries as [provider, providerOps] (provider)}
    {@const isOnline = onlineProviders.has(provider)}
    <div data-testid="provider-card" class="card bg-surface-100-900 mb-4 p-4">
      <div class="mb-3 flex items-center gap-2 text-base font-semibold">
        {provider}
        <span class={isOnline ? 'badge preset-filled-success-500' : 'badge preset-tonal-surface'}>
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
            onclick={() => onOpen(op, provider)}
          >
            {op.ui_hint?.label || op.name}
          </button>
        {/each}
      </div>
    </div>
  {/each}
{/if}
