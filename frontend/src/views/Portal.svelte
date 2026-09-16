<script lang="ts">
  import { store } from '../lib/store.svelte.ts';
  import { compareAppsByCategory } from '../lib/sort.js';
  import type { App } from '../api/api.js';

  type PortalApp = App & {
    _version?: string;
    _latest_apk_id?: string;
    _filename?: string;
  };

  type SortDirection = 'asc' | 'desc' | null;

  let query = $state('');
  let category = $state('');
  let sortDirection = $state<SortDirection>(null);

  const portalApps = $derived(store.allApps as PortalApp[]);
  const categories = $derived(Object.keys(store.settings.categories || {}).sort());

  const filtered = $derived.by(() => {
    let list = [...portalApps];
    const q = query.toLowerCase().trim();
    if (q) {
      list = list.filter(
        (a) => (a.name || '').toLowerCase().includes(q) || (a.id || '').toLowerCase().includes(q)
      );
    }
    if (category) {
      list = list.filter((a) => (a.categories || []).includes(category));
    }
    if (sortDirection) {
      list = [...list].sort((a, b) => compareAppsByCategory(a, b, sortDirection!));
    }
    return list;
  });

  function toggleSort(): void {
    sortDirection = sortDirection === null ? 'asc' : sortDirection === 'asc' ? 'desc' : null;
  }

  function isSelfHosted(app: { overrideSource?: string | null; url?: string }): boolean {
    return (
      app.overrideSource === 'HTML' && !!app.url && app.url.includes('/scrape-index.html')
    );
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

  function categoryStyle(name: string): string {
    const code = (store.settings.categories || {})[name];
    if (!code) return '';
    const r = (code >>> 16) & 0xff;
    const g = (code >>> 8) & 0xff;
    const b = code & 0xff;
    return `background: rgba(${r}, ${g}, ${b}, 0.15); border-color: rgba(${r}, ${g}, ${b}, 0.4); color: rgb(${Math.min(r + 60, 255)}, ${Math.min(g + 60, 255)}, ${Math.min(b + 60, 255)});`;
  }
</script>

<section class="mb-8 pt-16 pb-10 text-center">
  <h1 class="h1 mb-4 bg-gradient-to-br from-white to-surface-600-400 bg-clip-text text-[3rem] font-extrabold leading-[1.15] tracking-[-1.5px] text-transparent max-md:text-[2.25rem]">Android 端末のプロビジョニングを快適に</h1>
  <p class="mt-2 text-surface-700-300">
    Obtainium を活用して、必要なアプリや自作/野良 APK を一括インストール・自動アップデート管理するためのローカルリポジトリです。
  </p>

  <div class="card mt-6 bg-surface-100-900 border border-surface-200-800 p-6 backdrop-blur">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="size-8 shrink-0 text-primary-500"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
      <div>
        <h3 class="h4">Obtainium 一括インポート用 JSON</h3>
        <p class="mt-1 text-sm text-surface-700-300">
          ダウンロードした JSON を Obtainium の <strong>Import / Export → Obtainium Import</strong> で選択すると、全アプリを一発で登録できます。
        </p>
      </div>
    </div>
    <div class="mt-4">
      <a href="/obtainium-export.json" download="obtainium-export.json" class="btn preset-filled-primary-500" id="obtainium-download-btn">
        <span class="btn-text">Obtainium 用 JSON をダウンロード</span>
      </a>
    </div>
    <div class="mt-4 text-xs text-surface-600-400">
      <span>このサイトは <strong>Cloudflare Access</strong> で保護されています。アクセス時に表示される認証画面で、利用可能な任意の ID プロバイダーでサインインしてください。</span>
    </div>
  </div>
</section>

<section class="pt-10 pb-20">
  <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
    <h2 class="h3 mb-0">登録アプリ一覧</h2>
    <div class="flex flex-wrap items-center gap-3">
      <select id="portal-category-filter" class="select w-auto" bind:value={category}>
        <option value="">すべてのカテゴリ</option>
        {#each categories as cat}<option value={cat}>{cat}</option>{/each}
      </select>
      <div class="flex w-[320px] items-center rounded-full border border-surface-200-800 bg-surface-100-900 px-5 py-2 transition-all focus-within:border-primary-500 focus-within:shadow-[0_0_10px_rgba(124,77,255,0.15)] max-md:w-full">
        <input type="text" id="app-search-input" class="w-full border-none bg-transparent text-sm text-surface-900-100 outline-none placeholder:text-surface-600-400" placeholder="アプリ名で検索..." bind:value={query}>
      </div>
    </div>
  </div>

  <div class="table-wrap card bg-surface-100-900 border border-surface-200-800">
    <table class="table" data-testid="apps-table">
      <thead>
        <tr>
          <th class="col-name">アプリ名</th>
          <th class="col-category">
            <button type="button" id="portal-sort-category" class="flex cursor-pointer items-center gap-1" onclick={toggleSort}>
              カテゴリ <span id="portal-sort-icon" class="opacity-60">{sortDirection === 'asc' ? '▲' : sortDirection === 'desc' ? '▼' : '↕'}</span>
            </button>
          </th>
          <th class="col-source">ソース元</th>
          <th class="col-version">追跡バージョン</th>
          <th class="col-actions">アクション</th>
        </tr>
      </thead>
      <tbody id="apps-table-body">
        {#if filtered.length === 0}
          <tr data-testid="empty-row">
            <td colspan="5">
              <div class="flex flex-col items-center justify-center py-16 text-center text-surface-700-300"><p>該当するアプリが見つかりません。</p></div>
            </td>
          </tr>
        {:else}
          {#each filtered as app (app.id)}
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
                    {#each app.categories as cat}<span class="chip" data-testid="category-tag" style={categoryStyle(cat)}>{cat}</span>{/each}
                  {:else}
                    <span class="chip border border-dashed border-surface-300-700" data-testid="category-tag">未設定</span>
                  {/if}
                </div>
              </td>
              <td class="col-source">
                <div class="flex items-center gap-2.5">
                  <span class="badge {selfHosted ? 'preset-filled-secondary-500' : 'preset-filled-success-500'}">{selfHosted ? 'Self-Hosted' : 'Official'}</span>
                  <span class="text-sm font-medium text-surface-700-300">{app.overrideSource || 'Auto Detect'}</span>
                </div>
              </td>
              <td class="col-version"><span class="rounded border border-secondary-500/10 bg-secondary-500/5 px-1.5 py-0.5 font-mono text-sm text-surface-900-100">{selfHosted && app._version ? app._version : 'Tracked on source'}</span></td>
              <td class="col-actions">
                <div class="flex items-center gap-2">
                  <a href={obtainiumLink(app)} class="btn preset-filled-primary-500 [--btn-size:var(--text-sm)]"><span>Obtainium に追加</span></a>
                  {#if selfHosted}
                    <a href={downloadUrl(app)} class="btn preset-tonal [--btn-size:var(--text-sm)]" title="Direct APK Download">↓</a>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</section>
