<script lang="ts">
  import { Combobox, useListCollection } from '@skeletonlabs/skeleton-svelte';
  import FilterDatePicker from './FilterDatePicker.svelte';

  let {
    status = $bindable(''),
    from = $bindable(''),
    to = $bindable(''),
    op = $bindable(''),
    limit = $bindable(25),
    onApply,
    onReset,
  }: {
    status?: string;
    from?: string;
    to?: string;
    op?: string;
    limit?: number;
    onApply: () => void;
    onReset: () => void;
  } = $props();

  const ALL_STATUS = '__all__';

  const statusOptions = [
    { label: 'all', value: ALL_STATUS },
    { label: 'pending', value: 'pending' },
    { label: 'claimed', value: 'claimed' },
    { label: 'succeeded', value: 'succeeded' },
    { label: 'failed', value: 'failed' },
    { label: 'timeout', value: 'timeout' },
    { label: 'cancelled', value: 'cancelled' },
  ];
  const statusCollection = $derived(
    useListCollection({
      items: statusOptions,
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    })
  );

  const limitOptions = [
    { label: '10', value: '10' },
    { label: '25', value: '25' },
    { label: '50', value: '50' },
  ];
  const limitCollection = $derived(
    useListCollection({
      items: limitOptions,
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    })
  );

  const statusValue = $derived([status || ALL_STATUS]);
  const limitValue = $derived([String(limit)]);
</script>

<div class="card bg-surface-100-900 mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
  <div class="label">
    <label class="label-text" for="cmds-filter-status">Status</label>
    <Combobox
      placeholder="all"
      openOnClick
      collection={statusCollection}
      value={statusValue}
      onValueChange={(details) => {
        const next = details.value[0];
        status = next === undefined || next === ALL_STATUS ? '' : next;
      }}
    >
      <Combobox.Control>
        <Combobox.Input id="cmds-filter-status" readonly class="input" />
        <Combobox.Trigger data-testid="cmds-filter-status-trigger" />
      </Combobox.Control>
      <Combobox.Positioner>
        <Combobox.Content class="z-50">
          {#each statusOptions as item (item.value)}
            <Combobox.Item {item} data-testid={`cmds-filter-status-option-${item.value}`}>
              <Combobox.ItemText>{item.label}</Combobox.ItemText>
              <Combobox.ItemIndicator />
            </Combobox.Item>
          {/each}
        </Combobox.Content>
      </Combobox.Positioner>
    </Combobox>
  </div>
  <div class="label">
    <label class="label-text" for="cmds-filter-from">From</label>
    <FilterDatePicker id="cmds-filter-from" bind:value={from} />
  </div>
  <div class="label">
    <label class="label-text" for="cmds-filter-to">To</label>
    <FilterDatePicker id="cmds-filter-to" bind:value={to} />
  </div>
  <div class="label">
    <label class="label-text" for="cmds-filter-op">Op</label>
    <input type="text" id="cmds-filter-op" class="input" placeholder="e.g. config" bind:value={op} />
  </div>
  <div class="label">
    <label class="label-text" for="cmds-filter-limit">Page size</label>
    <Combobox
      placeholder="25"
      openOnClick
      collection={limitCollection}
      value={limitValue}
      onValueChange={(details) => {
        const next = parseInt(details.value[0] ?? '', 10);
        if ([10, 25, 50].includes(next)) limit = next;
      }}
    >
      <Combobox.Control>
        <Combobox.Input id="cmds-filter-limit" readonly class="input" />
        <Combobox.Trigger data-testid="cmds-filter-limit-trigger" />
      </Combobox.Control>
      <Combobox.Positioner>
        <Combobox.Content class="z-50">
          {#each limitOptions as item (item.value)}
            <Combobox.Item {item} data-testid={`cmds-filter-limit-option-${item.value}`}>
              <Combobox.ItemText>{item.label}</Combobox.ItemText>
              <Combobox.ItemIndicator />
            </Combobox.Item>
          {/each}
        </Combobox.Content>
      </Combobox.Positioner>
    </Combobox>
  </div>
  <div class="flex items-end gap-2">
    <button type="button" class="btn preset-filled-primary-500" id="cmds-filter-apply" onclick={onApply}>
      適用
    </button>
    <button type="button" class="btn preset-tonal" id="cmds-filter-reset" onclick={onReset}>
      リセット
    </button>
  </div>
</div>
