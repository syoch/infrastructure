<script lang="ts">
  import { store } from '../lib/store.svelte.ts';
  import { compareAppsByCategory } from '../lib/sort.js';
  import type { App } from '../api/api.js';
  import PortalAppsTable from '../components/obtainium/PortalAppsTable.svelte';

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
        a => (a.name || '').toLowerCase().includes(q) || (a.id || '').toLowerCase().includes(q)
      );
    }
    if (category) {
      list = list.filter(a => (a.categories || []).includes(category));
    }
    if (sortDirection) {
      list = [...list].sort((a, b) => compareAppsByCategory(a, b, sortDirection!));
    }
    return list;
  });

  function toggleSort(): void {
    sortDirection = sortDirection === null ? 'asc' : sortDirection === 'asc' ? 'desc' : null;
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

<div id="portal-view">
  <section class="mb-8 pt-16 pb-10 text-center">
    <h1
      class="h1 mb-4 bg-gradient-to-br from-white to-surface-600-400 bg-clip-text text-[3rem] font-extrabold leading-[1.15] tracking-[-1.5px] text-transparent max-md:text-[2.25rem]"
    >
      Android 端末のプロビジョニングを快適に
    </h1>
    <p class="mt-2 text-surface-700-300">
      Obtainium を活用して、必要なアプリや自作/野良 APK
      を一括インストール・自動アップデート管理するためのローカルリポジトリです。
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
            ダウンロードした JSON を Obtainium の <strong>Import / Export → Obtainium Import</strong
            > で選択すると、全アプリを一発で登録できます。
          </p>
        </div>
      </div>
      <div class="mt-4">
        <a
          href="/obtainium-export.json"
          download="obtainium-export.json"
          class="btn preset-filled-primary-500"
          id="obtainium-download-btn"
        >
          <span class="btn-text">Obtainium 用 JSON をダウンロード</span>
        </a>
      </div>
      <div class="mt-4 text-xs text-surface-600-400">
        <span
          >このサイトは <strong>Cloudflare Access</strong> で保護されています。アクセス時に表示される認証画面で、利用可能な任意の
          ID プロバイダーでサインインしてください。</span
        >
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
        <div
          class="flex w-[320px] items-center rounded-full border border-surface-200-800 bg-surface-100-900 px-5 py-2 transition-all focus-within:border-primary-500 focus-within:shadow-[0_0_10px_rgba(124,77,255,0.15)] max-md:w-full"
        >
          <input
            type="text"
            id="app-search-input"
            class="w-full border-none bg-transparent text-sm text-surface-900-100 outline-none placeholder:text-surface-600-400"
            placeholder="アプリ名で検索..."
            bind:value={query}
          />
        </div>
      </div>
    </div>

    <PortalAppsTable apps={filtered} {categoryStyle} {sortDirection} onToggleSort={toggleSort} />
  </section>
</div>
