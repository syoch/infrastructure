<script lang="ts">
  import { store, loadAllData } from '../lib/store.svelte.ts';
  import { goto as navigate } from '$app/navigation';
  import AppModal from '../components/AppModal.svelte';
  import CategoryModal from '../components/CategoryModal.svelte';
  import {
    saveSettings,
    compileSettings,
    deleteApp,
    importObtainiumConfig,
    restoreBackup,
    type App,
  } from '../api/api.js';
  import { showToast, getCategoryColorStyle, validateUrlSourceMatch } from '../lib/ui.js';
  import { showCustomToast } from '../lib/toast.ts';
  import { compareAppsByCategory } from '../lib/sort.ts';

  let {
    routeName = 'dashboard',
    params = {},
  }: { routeName?: string; params?: Record<string, string> } = $props();

  type SortDirection = 'asc' | 'desc' | null;

  let sortDirection = $state<SortDirection>(null);

  let theme = $state('system');
  let checkInterval = $state<string | number>('');
  let checkOnStartup = $state(false);
  let prerelease = $state(false);
  let allowSourceChange = $state(false);
  let restrictNotification = $state(false);
  let savingSettings = $state(false);

  let compileToast = $state<HTMLDivElement | null>(null);
  let compileBtn = $state<HTMLButtonElement | null>(null);
  let importJsonFile = $state<HTMLInputElement | null>(null);
  let restoreFileInput = $state<HTMLInputElement | null>(null);
  let restoreStrategy = $state('overwrite');
  let importBusy = $state(false);
  let restoreBusy = $state(false);

  const apps = $derived(store.dashboardApps);
  const categories = $derived(store.settings.categories || {});

  const sortedApps = $derived.by(() => {
    if (!sortDirection) return [...apps];
    return [...apps].sort((a, b) => compareAppsByCategory(a, b, sortDirection as 'asc' | 'desc'));
  });

  const appModalActive = $derived(
    (routeName === 'new' && params.type === 'app') ||
      (routeName === 'edit' && params.type === 'quick-app')
  );
  const appModalId = $derived(
    routeName === 'edit' && params.type === 'quick-app' ? params.id ?? null : null
  );
  const categoryModalActive = $derived(
    (routeName === 'new' && params.type === 'category') ||
      (routeName === 'edit' && params.type === 'category')
  );
  const categoryModalName = $derived(
    routeName === 'edit' && params.type === 'category' ? params.id ?? null : null
  );

  $effect(() => {
    const s = store.settings;
    theme = s.theme || 'system';
    checkInterval =
      s.checkInterval !== undefined && s.checkInterval !== null ? String(s.checkInterval) : '';
    checkOnStartup = !!s.checkOnStartup;
    prerelease = !!s.includePreReleases;
    allowSourceChange = !!s.allowSourceChange;
    restrictNotification = !!s.backgroundRestrictedNotification;
  });

  function onKeydown(e: KeyboardEvent): void {
    if (e.key !== 'Escape') return;
    if (document.querySelector('.modal-backdrop.active')) navigate('/list');
  }

  function onSortClick(): void {
    if (sortDirection === null) sortDirection = 'asc';
    else if (sortDirection === 'asc') sortDirection = 'desc';
    else sortDirection = null;
  }

  function openQuickEdit(id: string): void {
    navigate(`/edit?type=quick-app&id=${encodeURIComponent(id)}`);
  }

  function openCategory(name: string): void {
    navigate(`/edit?type=category&id=${encodeURIComponent(name)}`);
  }

  function sourceLabel(app: App): string {
    const { valid, warning } = validateUrlSourceMatch(app.url, app.overrideSource);
    return !valid && warning ? `⚠️ ${app.overrideSource}` : app.overrideSource || 'Auto';
  }

  function sourceWarning(app: App): string | null {
    const { valid, warning } = validateUrlSourceMatch(app.url, app.overrideSource);
    return !valid ? warning : null;
  }

  async function onDeleteApp(id: string): Promise<void> {
    if (!confirm(`アプリ '${id}' を削除してもよろしいですか？`)) return;
    try {
      await deleteApp(id);
      navigate('/list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      alert('アプリの削除に失敗しました。');
    }
  }

  async function onCompile(): Promise<void> {
    if (compileBtn) compileBtn.disabled = true;
    try {
      await compileSettings();
      showToast(compileToast);
      await loadAllData();
    } catch (err) {
      console.error(err);
      alert('設定のコンパイルに失敗しました。');
    } finally {
      if (compileBtn) compileBtn.disabled = false;
    }
  }

  function onImportClick(): void {
    importJsonFile?.click();
  }

  async function onImportChange(e: Event): Promise<void> {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    importBusy = true;
    try {
      const text = await file.text();
      const json = JSON.parse(text);
      const res = await importObtainiumConfig(json);
      alert(res.message || 'インポートが完了しました。');
      await loadAllData();
    } catch (err) {
      console.error(err);
      alert('インポートに失敗しました。JSONファイルが壊れているか、内容が正しくありません。');
    } finally {
      importBusy = false;
      if (importJsonFile) importJsonFile.value = '';
    }
  }

  function onRestoreClick(): void {
    restoreFileInput?.click();
  }

  async function onRestoreChange(e: Event): Promise<void> {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    const strategy = restoreStrategy;
    const strategyText =
      strategy === 'overwrite'
        ? '【上書き】（既存データがすべて削除され、バックアップの内容に置き換わります）'
        : '【マージ】（既存のデータにバックアップの内容が追加・統合されます）';

    const confirmed = confirm(
      `バックアップファイルの復元を実行します。\n` +
        `選択したファイル: ${file.name}\n` +
        `復元モード: ${strategyText}\n\n` +
        `本当によろしいですか？`
    );
    if (!confirmed) {
      input.value = '';
      return;
    }

    restoreBusy = true;
    try {
      showCustomToast('リストアを実行しています。ページをリロードしないでください...', 'info', 5000);
      await restoreBackup(file, strategy);
      showCustomToast('リストアが完了しました！データを再読み込みします。', 'success', 3000);
      setTimeout(() => window.location.reload(), 1500);
    } catch (err) {
      console.error(err);
      alert(`リストアに失敗しました: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      restoreBusy = false;
      input.value = '';
    }
  }

  async function onDownloadBackup(e: MouseEvent): Promise<void> {
    e.preventDefault();
    try {
      const { getToken } = await import('../api/control_api.js');
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch('/api/backup', { headers });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || `Backup download failed: ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `portal_backup_${Date.now()}.tar.gz`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    }
  }

  async function onSettingsSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    const intervalStr =
      checkInterval === '' || checkInterval === null || checkInterval === undefined
        ? ''
        : String(checkInterval);
    const payload = {
      theme,
      checkInterval: intervalStr !== '' ? parseInt(intervalStr, 10) : null,
      checkOnStartup,
      includePreReleases: prerelease,
      allowSourceChange,
      backgroundRestrictedNotification: restrictNotification,
    };
    savingSettings = true;
    try {
      await saveSettings(payload);
      showCustomToast('グローバル設定を保存しました。', 'success');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast(
        err instanceof Error ? err.message : 'グローバル設定の保存に失敗しました。',
        'error'
      );
    } finally {
      savingSettings = false;
    }
  }
</script>

<svelte:window onkeydown={onKeydown} />

<section class="dashboard-header-section">
  <div class="dashboard-title-row">
    <div>
      <h1>アプリ管理ダッシュボード</h1>
      <p class="hero-subtitle" style="margin:4px 0 0 0;text-align:left;">リポジトリ内のアプリ追加・編集・削除および設定のコンパイルを行います。</p>
    </div>

    <div class="dashboard-header-actions" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
      <button id="import-json-btn" class="btn btn-secondary" style="border-color:var(--accent-primary);color:var(--accent-primary);" disabled={importBusy} onclick={onImportClick}>
        <span>{importBusy ? 'インポート中...' : '📥 JSONインポート'}</span>
      </button>
      <input type="file" id="import-json-file" accept=".json" style="display:none;" bind:this={importJsonFile} onchange={onImportChange} />
      <button id="add-app-btn" class="btn btn-secondary" style="border-color:var(--accent-secondary);color:var(--accent-secondary);" onclick={() => navigate('/new?type=app')}>
        <span>➕ 新規アプリ登録</span>
      </button>
      <button id="compile-btn" class="btn btn-primary" bind:this={compileBtn} onclick={onCompile}>
        <span>設定をコンパイルして反映</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="btn-icon" style="width:16px;height:16px;color:#000;">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" fill="none"/>
        </svg>
      </button>
    </div>
  </div>
  <div id="compile-toast" class="toast-message hidden" bind:this={compileToast}>反映しました！</div>
</section>

<section class="categories-bar-section" style="margin-bottom:32px;background:var(--bg-card);padding:20px;border:1px solid var(--border-color);border-radius:var(--radius-lg);backdrop-filter:blur(20px);">
  <h3 style="font-size:0.85rem;color:var(--color-text-secondary);margin-bottom:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">カテゴリ一覧と編集</h3>
  <div id="dashboard-categories-bar" class="category-tags" style="gap:8px;display:flex;flex-wrap:wrap;align-items:center;">
    {#each Object.entries(categories) as [catName, colorCode] (catName)}
      <button
        type="button"
        class="category-tag interactive-tag"
        data-name={catName}
        style={getCategoryColorStyle(colorCode)}
        onclick={() => openCategory(catName)}
      >{catName}</button>
    {/each}
    <button id="add-category-btn" class="category-tag tag-none interactive-tag" style="background:rgba(255,255,255,0.02);border-style:dashed;cursor:pointer;border-radius:var(--radius-sm);padding:4px 10px;" onclick={() => navigate('/new?type=category')}>
      ➕ 新規カテゴリ追加
    </button>
  </div>
</section>

<section class="dashboard-list-section">
  <h2 class="section-title">登録アプリ一覧</h2>
  <div class="apps-table-container">
    <table class="apps-table">
      <thead>
        <tr>
          <th>アプリ名 / ID</th>
          <!-- svelte-ignore a11y_no_noninteractive_element_interactions a11y_click_events_have_key_events -->
          <th id="dashboard-sort-category" class="sortable" style="cursor:pointer;user-select:none;" onclick={onSortClick}>
            カテゴリ <span id="dashboard-sort-icon" class="sort-icon" style="opacity:0.6;margin-left:4px;">{sortDirection === 'asc' ? '▲' : sortDirection === 'desc' ? '▼' : '↕'}</span>
          </th>
          <th>ソースURL</th>
          <th style="text-align:right;padding-right:32px;">操作</th>
        </tr>
      </thead>
      <tbody id="dashboard-apps-list">
        {#if sortedApps.length === 0}
          <tr>
            <td colspan="4" style="text-align:center;padding:32px;color:var(--color-text-muted);">登録されているアプリがありません。新規アプリ登録から追加してください。</td>
          </tr>
        {:else}
          {#each sortedApps as app (app.id)}
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions a11y_click_events_have_key_events -->
            <tr
              class="app-row"
              onclick={(e) => {
                const target = e.target as HTMLElement;
                if (target.closest('button') || target.closest('.category-tag')) return;
                openQuickEdit(app.id);
              }}
            >
              <td>
                <div class="app-identity">
                  <span class="app-name-text">{app.name}</span>
                  <span class="app-package-text">{app.id}</span>
                </div>
              </td>
              <td>
                <div class="category-tags">
                  {#if app.categories && app.categories.length > 0}
                    {#each app.categories as cat (cat)}
                      <button type="button" class="category-tag" data-cat={cat} style={getCategoryColorStyle(categories[cat])} onclick={() => openCategory(cat)}>{cat}</button>
                    {/each}
                  {:else}
                    <span class="color-text-muted">-</span>
                  {/if}
                </div>
              </td>
              <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                <span style="color:var(--accent-secondary);font-size:0.85rem;">{app.url}</span>
                {#if sourceWarning(app)}
                  <div class="app-warning-text" title={sourceWarning(app)}>{sourceWarning(app)}</div>
                {/if}
              </td>
              <td style="text-align:right;">
                <div class="table-actions" style="justify-content:flex-end;gap:8px;">
                  <span class="app-source-badge">{sourceLabel(app)}</span>
                  <button class="btn btn-secondary btn-sm quick-edit-btn" onclick={() => openQuickEdit(app.id)}>簡易編集</button>
                  <button class="btn btn-secondary btn-sm delete-app-btn" style="color:#ff5252;border-color:rgba(255,82,82,0.2);" onclick={() => onDeleteApp(app.id)}>削除</button>
                </div>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</section>

<section class="dashboard-settings-section" style="margin-top:32px;background:var(--bg-card);padding:24px;border:1px solid var(--border-color);border-radius:var(--radius-lg);backdrop-filter:blur(20px);">
  <h3 style="font-size:0.85rem;color:var(--color-text-secondary);margin-bottom:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">Obtainium グローバル設定 (Global Settings)</h3>
  <p class="hero-subtitle" style="margin:0 0 20px 0;text-align:left;font-size:0.85rem;color:var(--color-text-muted);">Obtainium アプリ全体の共通動作や表示テーマなどの設定を管理します。</p>

  <form id="global-settings-form" onsubmit={onSettingsSubmit}>
    <div class="form-row" style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
      <div class="form-group" style="flex:1;min-width:200px;">
        <label for="global-setting-theme" style="display:block;font-size:0.8rem;font-weight:600;margin-bottom:6px;color:var(--color-text-secondary);">テーマ (theme)</label>
        <select id="global-setting-theme" class="filter-select" style="width:100%;background:rgba(255,255,255,0.05);color:var(--color-text-primary);border:1px solid var(--border-color);border-radius:var(--radius-sm);padding:8px 12px;outline:none;cursor:pointer;transition:var(--transition-smooth);" bind:value={theme}>
          <option value="system">システム同期 (system)</option>
          <option value="dark">ダークモード (dark)</option>
          <option value="light">ライトモード (light)</option>
        </select>
      </div>

      <div class="form-group" style="flex:1;min-width:200px;">
        <label for="global-setting-check-interval" style="display:block;font-size:0.8rem;font-weight:600;margin-bottom:6px;color:var(--color-text-secondary);">アップデートチェック間隔 (checkInterval / 時間)</label>
        <input type="number" id="global-setting-check-interval" min="0" placeholder="例: 24" style="width:100%;background:rgba(255,255,255,0.05);color:var(--color-text-primary);border:1px solid var(--border-color);border-radius:var(--radius-sm);padding:8px 12px;outline:none;transition:var(--transition-smooth);" bind:value={checkInterval} />
      </div>
    </div>

    <div class="checkbox-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;margin-bottom:24px;">
      <label class="checkbox-label" style="display:flex;align-items:center;gap:8px;font-size:0.85rem;cursor:pointer;color:var(--color-text-secondary);">
        <input type="checkbox" id="global-setting-check-on-startup" style="cursor:pointer;" bind:checked={checkOnStartup} />
        <span>起動時にアップデート確認 (checkOnStartup)</span>
      </label>

      <label class="checkbox-label" style="display:flex;align-items:center;gap:8px;font-size:0.85rem;cursor:pointer;color:var(--color-text-secondary);">
        <input type="checkbox" id="global-setting-prerelease" style="cursor:pointer;" bind:checked={prerelease} />
        <span>プレリリース版を含める (includePreReleases)</span>
      </label>

      <label class="checkbox-label" style="display:flex;align-items:center;gap:8px;font-size:0.85rem;cursor:pointer;color:var(--color-text-secondary);">
        <input type="checkbox" id="global-setting-allow-source-change" style="cursor:pointer;" bind:checked={allowSourceChange} />
        <span>ソース元の変更を許可 (allowSourceChange)</span>
      </label>

      <label class="checkbox-label" style="display:flex;align-items:center;gap:8px;font-size:0.85rem;cursor:pointer;color:var(--color-text-secondary);">
        <input type="checkbox" id="global-setting-restrict-notification" style="cursor:pointer;" bind:checked={restrictNotification} />
        <span>バックグラウンド制限警告を表示 (backgroundRestrictedNotification)</span>
      </label>
    </div>

    <div style="display:flex;justify-content:flex-end;">
      <button type="submit" class="btn btn-primary" disabled={savingSettings}>
        <span>{savingSettings ? '保存中...' : 'グローバル設定を保存'}</span>
      </button>
    </div>
  </form>
</section>

<section class="dashboard-system-section" style="margin-top:32px;background:var(--bg-card);padding:24px;border:1px solid var(--border-color);border-radius:var(--radius-lg);backdrop-filter:blur(20px);">
  <h3 style="font-size:0.85rem;color:var(--color-text-secondary);margin-bottom:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">システムバックアップ / リストア</h3>
  <p class="hero-subtitle" style="margin:0 0 16px 0;text-align:left;font-size:0.85rem;color:var(--color-text-muted);">データベースのレコードおよびアップロードされた APK ファイルを一括してバックアップ・復元します。</p>

  <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;">
    <a href="/api/backup" id="download-backup-btn" class="btn btn-secondary" style="border-color:var(--accent-primary);color:var(--accent-primary);text-decoration:none;display:inline-flex;align-items:center;" onclick={onDownloadBackup}>
      <span>📤 バックアップをダウンロード</span>
    </a>

    <div style="display:flex;align-items:center;gap:8px;border-left:1px solid var(--border-color);padding-left:16px;flex-wrap:wrap;">
      <select id="restore-strategy" class="filter-select" style="background:rgba(255,255,255,0.05);color:var(--color-text-primary);border:1px solid var(--border-color);border-radius:var(--radius-sm);padding:8px 12px;outline:none;cursor:pointer;height:38px;" bind:value={restoreStrategy}>
        <option value="overwrite">上書き復元 (Overwrite)</option>
        <option value="merge">マージ復元 (Merge)</option>
      </select>
      <button id="restore-btn" class="btn btn-secondary" style="border-color:var(--accent-secondary);color:var(--accent-secondary);height:38px;" disabled={restoreBusy} onclick={onRestoreClick}>
        <span>{restoreBusy ? 'リストア中...' : '📥 バックアップからリストア'}</span>
      </button>
      <input type="file" id="restore-file-input" accept=".tar.gz" style="display:none;" bind:this={restoreFileInput} onchange={onRestoreChange} />
    </div>
  </div>
</section>

<AppModal active={appModalActive} appId={appModalId} />
<CategoryModal active={categoryModalActive} categoryName={categoryModalName} />
