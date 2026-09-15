<script lang="ts">
  import { store } from '../lib/store.svelte.ts';
  import { compareAppsByCategory } from '../lib/sort.js';
  import type { App } from '../../js/api.js';

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

<section class="hero-section">
  <h1>Android 端末のプロビジョニングを快適に</h1>
  <p class="hero-subtitle">Obtainium を活用して、必要なアプリや自作/野良 APK を一括インストール・自動アップデート管理するためのローカルリポジトリです。</p>

  <div class="main-import-card">
    <div class="import-card-header">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="card-header-icon">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
      <div>
        <h3>Obtainium 一括インポート用 JSON</h3>
        <p>ダウンロードした JSON を Obtainium の <strong>Import / Export → Obtainium Import</strong> で選択すると、全アプリを一発で登録できます。</p>
      </div>
    </div>
    <div class="main-import-actions">
      <a href="/obtainium-export.json" download="obtainium-export.json" class="btn btn-primary" id="obtainium-download-btn">
        <span class="btn-text">Obtainium 用 JSON をダウンロード</span>
      </a>
    </div>
    <div class="card-note" style="margin-top: 16px;">
      <span>このサイトは <strong>Cloudflare Access</strong> で保護されています。アクセス時に表示される認証画面で、利用可能な任意の ID プロバイダーでサインインしてください。</span>
    </div>
  </div>
</section>

<section class="directory-section">
  <div class="directory-header" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; margin-bottom:24px;">
    <h2 class="section-title" style="margin-bottom:0;">登録アプリ一覧</h2>
    <div class="filter-controls" style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
      <select id="portal-category-filter" class="filter-select" bind:value={category}>
        <option value="">すべてのカテゴリ</option>
        {#each categories as cat}<option value={cat}>{cat}</option>{/each}
      </select>
      <div class="search-box" style="margin-top:0;">
        <input type="text" id="app-search-input" placeholder="アプリ名で検索..." bind:value={query}>
      </div>
    </div>
  </div>

  <div class="apps-table-container">
    <table class="apps-table">
      <thead>
        <tr>
          <th class="col-name">アプリ名</th>
          <th class="col-category sortable" id="portal-sort-category" style="cursor:pointer; user-select:none;" onclick={toggleSort}>
            カテゴリ <span id="portal-sort-icon" class="sort-icon" style="opacity:0.6; margin-left:4px;">{sortDirection === 'asc' ? '▲' : sortDirection === 'desc' ? '▼' : '↕'}</span>
          </th>
          <th class="col-source">ソース元</th>
          <th class="col-version">追跡バージョン</th>
          <th class="col-actions">アクション</th>
        </tr>
      </thead>
      <tbody id="apps-table-body">
        {#if filtered.length === 0}
          <tr class="empty-row">
            <td colspan="5">
              <div class="empty-state"><p>該当するアプリが見つかりません。</p></div>
            </td>
          </tr>
        {:else}
          {#each filtered as app (app.id)}
            {@const selfHosted = isSelfHosted(app)}
            <tr class="app-row">
              <td class="col-name">
                <div class="app-identity">
                  <span class="app-name-text">{app.name}</span>
                  <span class="app-package-text">{app.id}</span>
                </div>
              </td>
              <td class="col-category">
                <div class="category-tags">
                  {#if app.categories && app.categories.length}
                    {#each app.categories as cat}<span class="category-tag" style={categoryStyle(cat)}>{cat}</span>{/each}
                  {:else}
                    <span class="category-tag tag-none">未設定</span>
                  {/if}
                </div>
              </td>
              <td class="col-source">
                <div class="source-identity">
                  <span class="badge {selfHosted ? 'badge-self-hosted' : 'badge-official'}">{selfHosted ? 'Self-Hosted' : 'Official'}</span>
                  <span class="source-type">{app.overrideSource || 'Auto Detect'}</span>
                </div>
              </td>
              <td class="col-version"><span class="version-text">{selfHosted && app._version ? app._version : 'Tracked on source'}</span></td>
              <td class="col-actions">
                <div class="table-actions">
                  <a href={obtainiumLink(app)} class="btn btn-primary btn-sm"><span>Obtainium に追加</span></a>
                  {#if selfHosted}
                    <a href={downloadUrl(app)} class="btn btn-secondary btn-sm" title="Direct APK Download">↓</a>
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
