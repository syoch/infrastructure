<script lang="ts">
  import { untrack } from 'svelte';
  import { Combobox, useListCollection } from '@skeletonlabs/skeleton-svelte';
  import type { WebAppDetail } from '../../../api/app_portal_api.js';

  let {
    app,
    saving,
    message,
    onsubmit,
  }: {
    app: WebAppDetail;
    saving: boolean;
    message: string;
    onsubmit: (e: SubmitEvent) => void;
  } = $props();

  const statusOptions = [
    { label: 'active', value: 'active' },
    { label: 'archived', value: 'archived' },
  ];
  const statusCollection = $derived(
    useListCollection({
      items: statusOptions,
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    })
  );

  let status = $state(untrack(() => (app.status === 'archived' ? 'archived' : 'active')));
  $effect(() => {
    status = app.status === 'archived' ? 'archived' : 'active';
  });
</script>

<section class="card bg-surface-100-900 p-6">
  <header class="mb-4"><h2 class="h4 m-0">設定</h2></header>
  {#if message}<p class="mb-2 text-sm text-success-500">{message}</p>{/if}
  <form id="app-edit-form" class="grid gap-4 sm:grid-cols-2" onsubmit={onsubmit}>
    <label class="label">
      <span class="label-text">アプリ名 *</span>
      <input id="ef-name" name="name" class="input" required value={app.name}>
    </label>
    <label class="label">
      <span class="label-text">説明</span>
      <input id="ef-description" name="description" class="input" value={app.description || ''}>
    </label>
    <label class="label">
      <span class="label-text">公開 URL</span>
      <input id="ef-url" name="url" class="input" value={app.url || ''}>
    </label>
    <label class="label">
      <span class="label-text">プロジェクトディレクトリ *</span>
      <input id="ef-dir" name="project_directory" class="input" required value={app.project_directory}>
    </label>
    <label class="label">
      <span class="label-text">OpenCode セッション ID *</span>
      <input id="ef-session" name="opencode_session_id" class="input" required value={app.opencode_session_id}>
    </label>
    <label class="label">
      <span class="label-text">bridge device id *</span>
      <input id="ef-bridge" name="bridge_device_id" class="input" required value={app.bridge_device_id}>
    </label>
    <label class="label">
      <span class="label-text">タグ (カンマ区切り)</span>
      <input id="ef-tags" name="tags" class="input" value={(app.tags || []).join(', ')}>
    </label>
    <div class="label">
      <label class="label-text" for="ef-status">ステータス</label>
      <input type="hidden" name="status" value={status}>
      <Combobox
        placeholder="active"
        openOnClick
        collection={statusCollection}
        value={[status]}
        onValueChange={(details) => {
          status = details.value[0] ?? 'active';
        }}
      >
        <Combobox.Control>
          <Combobox.Input id="ef-status" readonly class="input" />
          <Combobox.Trigger data-testid="ef-status-trigger" />
        </Combobox.Control>
        <Combobox.Positioner>
          <Combobox.Content class="z-50">
            {#each statusOptions as item (item.value)}
              <Combobox.Item {item} data-testid={`ef-status-option-${item.value}`}>
                <Combobox.ItemText>{item.label}</Combobox.ItemText>
                <Combobox.ItemIndicator />
              </Combobox.Item>
            {/each}
          </Combobox.Content>
        </Combobox.Positioner>
      </Combobox>
    </div>
    <div class="sm:col-span-2">
      <button type="submit" class="btn preset-filled-primary-500" disabled={saving}>
        {saving ? '保存中…' : '設定を保存'}
      </button>
    </div>
  </form>
</section>
