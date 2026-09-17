<script lang="ts">
  import type { WebApp } from '../../api/app_portal_api.js';

  let { apps, onOpen }: { apps: WebApp[]; onOpen: (a: WebApp) => void } = $props();
</script>

<div id="apps-list">
  {#if apps.length === 0}
    <p class="text-surface-600-400">登録されたアプリはありません。</p>
  {:else}
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each apps as a (a.id)}
        <div
          class="card cursor-pointer bg-surface-50-950 p-4 transition hover:brightness-105"
          role="button"
          tabindex="0"
          data-testid="app-card"
          onclick={() => onOpen(a)}
          onkeydown={(e) => e.key === 'Enter' && onOpen(a)}
        >
          <div class="flex items-start justify-between gap-2">
            <h3 class="h5 m-0">{a.name}</h3>
            <span class="badge preset-tonal-surface">{a.status}</span>
          </div>
          <p class="my-2 text-sm text-surface-700-300">{a.description || ''}</p>
          <div class="mb-2 flex flex-wrap gap-1">
            {#each a.tags || [] as t}<span class="chip preset-tonal">{t}</span>{/each}
          </div>
          <div class="text-xs break-all text-surface-600-400">{a.project_directory}</div>
        </div>
      {/each}
    </div>
  {/if}
</div>
