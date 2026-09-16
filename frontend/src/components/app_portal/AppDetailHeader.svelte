<script lang="ts">
  import type { WebAppDetail } from '../../api/app_portal_api.js';
  import { safeURL } from '../../lib/ui.js';

  let { app, onDelete }: { app: WebAppDetail; onDelete: () => void } = $props();
</script>

<section class="card bg-surface-100-900 p-6">
  <a class="anchor text-sm" href="#/apps">&larr; アプリ一覧</a>
  <header class="mt-2 flex flex-wrap items-center justify-between gap-3">
    <h2 class="h3 m-0">{app.name}</h2>
    <div class="flex flex-wrap items-center gap-2">
      {#if app.webui_url}
        <a class="btn preset-tonal" href={safeURL(app.webui_url)} target="_blank" rel="noopener">セッションを開く</a>
      {:else}
        <span class="text-xs text-surface-600-400">セッションリンク未登録 (bridge 未接続)</span>
      {/if}
      <button class="btn preset-tonal text-error-500" id="app-delete-btn" onclick={onDelete}>削除</button>
    </div>
  </header>
  <div class="mt-4 flex flex-col gap-1 text-xs text-surface-600-400">
    <div>slug: <code>{app.slug}</code></div>
    {#if app.url}
      <div>URL: <a class="anchor" href={safeURL(app.url)} target="_blank" rel="noopener">{app.url}</a></div>
    {/if}
    <div>directory: <code>{app.project_directory}</code></div>
    <div>session: <code>{app.opencode_session_id}</code></div>
    <div>bridge: <code>{app.bridge_device_id}</code></div>
  </div>
</section>
