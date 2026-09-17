<script lang="ts">
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
    <label class="label">
      <span class="label-text">ステータス</span>
      <select id="ef-status" name="status" class="select">
        <option value="active" selected={app.status === 'active'}>active</option>
        <option value="archived" selected={app.status === 'archived'}>archived</option>
      </select>
    </label>
    <div class="sm:col-span-2">
      <button type="submit" class="btn preset-filled-primary-500" disabled={saving}>
        {saving ? '保存中…' : '設定を保存'}
      </button>
    </div>
  </form>
</section>
