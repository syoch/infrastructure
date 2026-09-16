<script lang="ts">
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
</script>

<div class="card bg-surface-100-900 mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
  <label class="label" for="cmds-filter-status">
    <span class="label-text">Status</span>
    <select id="cmds-filter-status" class="select" bind:value={status}>
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
    <input type="datetime-local" id="cmds-filter-from" class="input" bind:value={from} />
  </label>
  <label class="label" for="cmds-filter-to">
    <span class="label-text">To</span>
    <input type="datetime-local" id="cmds-filter-to" class="input" bind:value={to} />
  </label>
  <label class="label" for="cmds-filter-op">
    <span class="label-text">Op</span>
    <input type="text" id="cmds-filter-op" class="input" placeholder="e.g. config" bind:value={op} />
  </label>
  <label class="label" for="cmds-filter-limit">
    <span class="label-text">Page size</span>
    <select id="cmds-filter-limit" class="select" bind:value={limit}>
      <option value={10}>10</option>
      <option value={25}>25</option>
      <option value={50}>50</option>
    </select>
  </label>
  <div class="flex items-end gap-2">
    <button type="button" class="btn preset-filled-primary-500" id="cmds-filter-apply" onclick={onApply}>
      適用
    </button>
    <button type="button" class="btn preset-tonal" id="cmds-filter-reset" onclick={onReset}>
      リセット
    </button>
  </div>
</div>
