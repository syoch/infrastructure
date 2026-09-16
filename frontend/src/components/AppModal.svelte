<script lang="ts">
  import { store, loadAllData } from '../lib/store.svelte.ts';
  import { navigate } from '../lib/router.svelte.ts';
  import { saveApp, type SaveAppPayload, type App } from '../api/api.js';

  let {
    active = false,
    appId = null,
  }: { active?: boolean; appId?: string | null } = $props();

  let editMode = $state(false);
  let pkgId = $state('');
  let appName = $state('');
  let appUrl = $state('');
  let appSource = $state('GitHub');
  let urlDisabled = $state(false);
  let customCategories = $state('');
  let checked = $state<Record<string, boolean>>({});

  let lastKey: string | null = null;

  const categories = $derived(Object.keys(store.settings.categories || {}));

  $effect(() => {
    const key = active ? (appId ?? '__new__') : null;
    if (key === null) {
      lastKey = null;
      return;
    }
    if (key === lastKey) return;
    const app = appId ? store.dashboardApps.find((a) => a.id === appId) : null;
    if (appId && !app) return;
    lastKey = key;
    applyApp(app ?? null);
  });

  function applyApp(app: App | null): void {
    editMode = !!app;
    pkgId = app ? app.id : '';
    appName = app ? app.name : '';
    appUrl = app ? app.url || '' : '';
    appSource = app ? app.overrideSource || 'GitHub' : 'GitHub';
    const next: Record<string, boolean> = {};
    (app?.categories || []).forEach((c) => {
      next[c] = true;
    });
    checked = next;
    customCategories = '';
    if (appSource === 'HTML') {
      appUrl = '/scrape-index.html';
      urlDisabled = true;
    } else {
      urlDisabled = false;
    }
  }

  function onSourceChange(e: Event): void {
    const value = (e.currentTarget as HTMLSelectElement).value;
    appSource = value;
    if (value === 'HTML') {
      appUrl = '/scrape-index.html';
      urlDisabled = true;
    } else {
      if (appUrl === '/scrape-index.html') appUrl = '';
      urlDisabled = false;
    }
  }

  async function onSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    const selected = categories.filter((c) => checked[c]);
    const custom = customCategories
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
    const merged = Array.from(new Set([...selected, ...custom]));
    const existing = store.dashboardApps.find((a) => a.id === pkgId.trim());
    const payload: SaveAppPayload = {
      id: pkgId.trim(),
      name: appName.trim(),
      url: appUrl.trim(),
      overrideSource: appSource,
      categories: merged,
      additionalSettings: existing?.additionalSettings || {
        includePrereleases: false,
        fallbackToOlderReleases: true,
        versionDetection: true,
      },
    };
    try {
      await saveApp(payload);
      navigate('#list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      alert('保存に失敗しました。');
    }
  }

  function onDetail(): void {
    navigate(`#edit?type=app&id=${encodeURIComponent(pkgId)}`);
  }
</script>

<div id="app-modal" class="modal-backdrop" class:active={active}>
  <div class="modal-content">
    <button class="modal-close-btn" id="app-modal-close" type="button" aria-label="閉じる" onclick={() => navigate('#list')}>
      <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </button>

    <h2 class="card-title" id="app-modal-title">{editMode ? 'アプリ簡易編集' : 'アプリを登録する'}</h2>
    <p class="card-subtitle" id="app-modal-subtitle">
      {editMode ? `パッケージ ID: ${pkgId}` : 'アプリの基本情報を入力してください。'}
    </p>

    <form id="quick-app-form" onsubmit={onSubmit}>
      <input type="hidden" id="quick-app-edit-mode" value={editMode ? 'true' : 'false'} />

      <div class="form-group">
        <label for="quick-app-id">パッケージID (Package ID) <span class="required">*</span></label>
        <input type="text" id="quick-app-id" placeholder="e.g. com.termux" required disabled={editMode} bind:value={pkgId} />
      </div>

      <div class="form-group">
        <label for="quick-app-name">アプリ名 (App Name) <span class="required">*</span></label>
        <input type="text" id="quick-app-name" placeholder="e.g. Termux" required bind:value={appName} />
      </div>

      <div class="form-group">
        <label for="quick-app-url">ソースURL (GitHub / スクラップ対象) <span class="required">*</span></label>
        <input type="text" id="quick-app-url" placeholder="e.g. https://github.com/termux/termux-app" required disabled={urlDisabled} bind:value={appUrl} />
      </div>

      <div class="form-row">
        <div class="form-group col-6">
          <label for="quick-app-source">ソース元タイプ</label>
          <select id="quick-app-source" value={appSource} onchange={onSourceChange}>
            <option value="GitHub">GitHub</option>
            <option value="HTML">HTML (Self-Hosted / WebScrape)</option>
            <option value="F-Droid">F-Droid</option>
            <option value="GitLab">GitLab</option>
          </select>
        </div>
        <div class="form-group col-6">
          <span class="form-label">カテゴリの選択</span>
          <div id="quick-categories-checkboxes" style="display:flex;flex-direction:column;gap:6px;max-height:120px;overflow-y:auto;background:rgba(0,0,0,0.15);padding:8px 12px;border-radius:var(--radius-sm);border:1px solid var(--border-color);margin-bottom:8px;">
            {#if categories.length === 0}
              <div style="color:var(--color-text-muted);font-size:0.8rem;padding:4px 0;">登録済みのカテゴリがありません。</div>
            {:else}
              {#each categories as cat (cat)}
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:0.85rem;">
                  <input type="checkbox" name="app-category-checkbox" value={cat} bind:checked={checked[cat]} style="cursor:pointer;" />
                  <span>{cat}</span>
                </label>
              {/each}
            {/if}
          </div>
          <input type="text" id="quick-app-categories" placeholder="新規追加（カンマ区切り）" style="font-size:0.85rem;padding:6px 10px;" bind:value={customCategories} />
        </div>
      </div>

      <div class="form-actions" style="margin-top:28px;">
        <button type="submit" class="btn btn-primary" id="quick-save-btn">保存する</button>
        <button
          type="button"
          id="quick-detail-btn"
          class="btn btn-secondary"
          style={editMode
            ? 'display:inline-flex;border-color:var(--accent-secondary);color:var(--accent-secondary);'
            : 'display:none;border-color:var(--accent-secondary);color:var(--accent-secondary);'}
          onclick={onDetail}
        >詳細設定へ ⚙️</button>
        <button type="button" class="btn btn-secondary" id="quick-cancel-btn" onclick={() => navigate('#list')}>キャンセル</button>
      </div>
    </form>
  </div>
</div>
