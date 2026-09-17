<script lang="ts">
  import type { App } from '../api/api.js';
  import SortHeader from '../components/obtainium/SortHeader.svelte';

  type PortalApp = App & {
    _version?: string;
    _latest_apk_id?: string;
    _filename?: string;
  };

  let {
    apps,
    categoryStyle,
    sortDirection,
    onToggleSort,
  }: {
    apps: PortalApp[];
    categoryStyle: (name: string) => string;
    sortDirection: 'asc' | 'desc' | null;
    onToggleSort: () => void;
  } = $props();

  function isSelfHosted(app: { overrideSource?: string | null; url?: string }): boolean {
    return app.overrideSource === 'HTML' && !!app.url && app.url.includes('/scrape-index.html');
  }

  function obtainiumLink(app: { url?: string }): string {
    let resolved = app.url || '';
    if (resolved.startsWith('/')) resolved = window.location.origin + resolved;
    return `obtainium://${encodeURIComponent(resolved)}`;
  }

  function downloadUrl(app: { _latest_apk_id?: string; _filename?: string }): string {
    return app._latest_apk_id
      ? `/api/apps/download/${app._latest_apk_id}/${encodeURIComponent(app._filename || 'download.apk')}`
      : `/scrape-index.html`;
  }
</script>

<div class="table-wrap card bg-surface-100-900 border border-surface-200-800">
  <table class="table" data-testid="apps-table">
    <thead>
      <tr>
        <th class="col-name">アプリ名</th>
        <th class="col-category">
          <SortHeader
            id="portal-sort-category"
            iconId="portal-sort-icon"
            direction={sortDirection}
            onclick={onToggleSort}
          />
        </th>
        <th class="col-source">ソース元</th>
        <th class="col-version">追跡バージョン</th>
        <th class="col-actions">アクション</th>
      </tr>
    </thead>
    <tbody id="apps-table-body">
      {#if apps.length === 0}
        <tr data-testid="empty-row">
          <td colspan="5">
            <div
              class="flex flex-col items-center justify-center py-16 text-center text-surface-700-300"
            >
              <p>該当するアプリが見つかりません。</p>
            </div>
          </td>
        </tr>
      {:else}
        {#each apps as app (app.id)}
          {@const selfHosted = isSelfHosted(app)}
          <tr data-testid="app-row">
            <td class="col-name">
              <div class="flex flex-col gap-1">
                <span class="font-bold">{app.name}</span>
                <span class="font-mono text-xs text-surface-600-400">{app.id}</span>
              </div>
            </td>
            <td class="col-category">
              <div class="flex flex-wrap gap-1.5" data-testid="category-tags">
                {#if app.categories && app.categories.length}
                  {#each app.categories as cat}<span
                      class="chip"
                      data-testid="category-tag"
                      style={categoryStyle(cat)}>{cat}</span
                    >{/each}
                {:else}
                  <span
                    class="chip border border-dashed border-surface-300-700"
                    data-testid="category-tag">未設定</span
                  >
                {/if}
              </div>
            </td>
            <td class="col-source">
              <div class="flex items-center gap-2.5">
                <span
                  class="badge {selfHosted
                    ? 'preset-filled-secondary-500'
                    : 'preset-filled-success-500'}"
                  >{selfHosted ? 'Self-Hosted' : 'Official'}</span
                >
                <span class="text-sm font-medium text-surface-700-300"
                  >{app.overrideSource || 'Auto Detect'}</span
                >
              </div>
            </td>
            <td class="col-version"
              ><span
                class="rounded border border-secondary-500/10 bg-secondary-500/5 px-1.5 py-0.5 font-mono text-sm text-surface-900-100"
                >{selfHosted && app._version ? app._version : 'Tracked on source'}</span
              ></td
            >
            <td class="col-actions">
              <div class="flex items-center gap-2">
                <a
                  href={obtainiumLink(app)}
                  class="btn preset-filled-primary-500 [--btn-size:var(--text-sm)]"
                  ><span>Obtainium に追加</span></a
                >
                {#if selfHosted}
                  <a
                    href={downloadUrl(app)}
                    class="btn preset-tonal [--btn-size:var(--text-sm)]"
                    title="Direct APK Download">↓</a
                  >
                {/if}
              </div>
            </td>
          </tr>
        {/each}
      {/if}
    </tbody>
  </table>
</div>
