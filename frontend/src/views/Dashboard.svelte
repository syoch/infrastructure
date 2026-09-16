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
  import { getCategoryColorStyle, validateUrlSourceMatch } from '../lib/ui.js';
  import { showToast, showCustomToast } from '../lib/toast.ts';
  import { confirmDialog } from '../lib/dialogs.svelte.ts';
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
    const confirmed = await confirmDialog({
      title: 'アプリを削除',
      message: `アプリ '${id}' を削除してもよろしいですか？`,
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteApp(id);
      navigate('/list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast('アプリの削除に失敗しました。', 'error');
    }
  }

  async function onCompile(): Promise<void> {
    if (compileBtn) compileBtn.disabled = true;
    try {
      await compileSettings();
      showToast('反映しました！', 'success');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast('設定のコンパイルに失敗しました。', 'error');
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
      showCustomToast(res.message || 'インポートが完了しました。', 'success');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast(
        'インポートに失敗しました。JSONファイルが壊れているか、内容が正しくありません。',
        'error'
      );
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

    const confirmed = await confirmDialog({
      title: 'バックアップからリストア',
      message:
        `バックアップファイルの復元を実行します。\n` +
        `選択したファイル: ${file.name}\n` +
        `復元モード: ${strategyText}\n\n` +
        `本当によろしいですか？`,
      confirmText: '実行',
    });
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
      showCustomToast(
        `リストアに失敗しました: ${err instanceof Error ? err.message : String(err)}`,
        'error'
      );
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
      showCustomToast(err instanceof Error ? err.message : String(err), 'error');
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

<section class="dashboard-header-section mb-6">
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <h1 class="h2">アプリ管理ダッシュボード</h1>
      <p class="mt-1 text-sm text-surface-700-300">リポジトリ内のアプリ追加・編集・削除および設定のコンパイルを行います。</p>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <button id="import-json-btn" class="btn preset-tonal-primary-500" disabled={importBusy} onclick={onImportClick}>
        <span>{importBusy ? 'インポート中...' : '📥 JSONインポート'}</span>
      </button>
      <input type="file" id="import-json-file" accept=".json" class="hidden" bind:this={importJsonFile} onchange={onImportChange} />
      <button id="add-app-btn" class="btn preset-tonal-secondary-500" onclick={() => navigate('/new?type=app')}>
        <span>➕ 新規アプリ登録</span>
      </button>
      <button id="compile-btn" class="btn preset-filled-primary-500" bind:this={compileBtn} onclick={onCompile}>
        <span>設定をコンパイルして反映</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="size-4">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" fill="none" />
        </svg>
      </button>
    </div>
  </div>
</section>

<section class="categories-bar-section mb-8">
  <div class="card bg-surface-100-900 border border-surface-200-800 p-5 backdrop-blur">
    <h3 class="label-text mb-3 uppercase tracking-wide text-surface-700-300">カテゴリ一覧と編集</h3>
    <div id="dashboard-categories-bar" class="flex flex-wrap items-center gap-2">
      {#each Object.entries(categories) as [catName, colorCode] (catName)}
        <button
          type="button"
          class="chip cursor-pointer"
          data-testid="category-tag"
          data-name={catName}
          style={getCategoryColorStyle(colorCode)}
          onclick={() => openCategory(catName)}
        >{catName}</button>
      {/each}
      <button id="add-category-btn" class="chip cursor-pointer border border-dashed border-surface-300-700" onclick={() => navigate('/new?type=category')}>
        ➕ 新規カテゴリ追加
      </button>
    </div>
  </div>
</section>

<section class="dashboard-list-section mb-8" data-testid="dashboard-list-section">
  <h2 class="h3 mb-4">登録アプリ一覧</h2>
  <div class="table-wrap card bg-surface-100-900 border border-surface-200-800">
    <table class="table">
      <thead>
        <tr>
          <th>アプリ名 / ID</th>
          <th>
            <button id="dashboard-sort-category" type="button" class="flex cursor-pointer items-center gap-1" onclick={onSortClick}>
              カテゴリ <span id="dashboard-sort-icon" class="opacity-60">{sortDirection === 'asc' ? '▲' : sortDirection === 'desc' ? '▼' : '↕'}</span>
            </button>
          </th>
          <th>ソースURL</th>
          <th class="pr-8 text-right">操作</th>
        </tr>
      </thead>
      <tbody id="dashboard-apps-list">
        {#if sortedApps.length === 0}
          <tr data-testid="empty-row">
            <td colspan="4" class="p-8 text-center text-surface-600-400">登録されているアプリがありません。新規アプリ登録から追加してください。</td>
          </tr>
        {:else}
          {#each sortedApps as app (app.id)}
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions a11y_click_events_have_key_events -->
            <tr
              class="cursor-pointer"
              data-testid="app-row"
              onclick={(e) => {
                const target = e.target as HTMLElement;
                if (target.closest('button') || target.closest('[data-testid="category-tag"]')) return;
                openQuickEdit(app.id);
              }}
            >
              <td>
                <div class="app-identity flex flex-col gap-1">
                  <span class="font-bold" data-testid="app-name-text">{app.name}</span>
                  <span class="font-mono text-xs text-surface-600-400">{app.id}</span>
                </div>
              </td>
              <td>
                <div class="flex flex-wrap gap-1.5" data-testid="category-tags">
                  {#if app.categories && app.categories.length > 0}
                    {#each app.categories as cat (cat)}
                      <button type="button" class="chip cursor-pointer" data-testid="category-tag" data-cat={cat} style={getCategoryColorStyle(categories[cat])} onclick={() => openCategory(cat)}>{cat}</button>
                    {/each}
                  {:else}
                    <span class="text-surface-600-400">-</span>
                  {/if}
                </div>
              </td>
              <td class="max-w-[300px] overflow-hidden text-ellipsis whitespace-nowrap">
                <span class="text-sm text-secondary-500">{app.url}</span>
                {#if sourceWarning(app)}
                  <div class="text-xs text-warning-500" title={sourceWarning(app)}>{sourceWarning(app)}</div>
                {/if}
              </td>
              <td class="text-right">
                <div class="table-actions flex items-center justify-end gap-2">
                  <span class="badge preset-tonal">{sourceLabel(app)}</span>
                  <button class="btn preset-tonal btn-sm quick-edit-btn" onclick={() => openQuickEdit(app.id)}>簡易編集</button>
                  <button class="btn preset-tonal-error btn-sm delete-app-btn" onclick={() => onDeleteApp(app.id)}>削除</button>
                </div>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</section>

<section class="dashboard-settings-section mt-8">
  <div class="card bg-surface-100-900 border border-surface-200-800 p-6 backdrop-blur">
    <h3 class="label-text mb-3 uppercase tracking-wide text-surface-700-300">Obtainium グローバル設定 (Global Settings)</h3>
    <p class="mb-5 text-sm text-surface-600-400">Obtainium アプリ全体の共通動作や表示テーマなどの設定を管理します。</p>

    <form id="global-settings-form" onsubmit={onSettingsSubmit}>
      <div class="mb-4 flex flex-wrap gap-4">
        <div class="min-w-[200px] flex-1">
          <label for="global-setting-theme" class="label-text mb-1.5">テーマ (theme)</label>
          <select id="global-setting-theme" class="select" bind:value={theme}>
            <option value="system">システム同期 (system)</option>
            <option value="dark">ダークモード (dark)</option>
            <option value="light">ライトモード (light)</option>
          </select>
        </div>

        <div class="min-w-[200px] flex-1">
          <label for="global-setting-check-interval" class="label-text mb-1.5">アップデートチェック間隔 (checkInterval / 時間)</label>
          <input type="number" id="global-setting-check-interval" class="input" min="0" placeholder="例: 24" bind:value={checkInterval} />
        </div>
      </div>

      <div class="mb-6 grid gap-4" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr));">
        <label class="flex cursor-pointer items-center gap-2 text-sm text-surface-700-300">
          <input type="checkbox" id="global-setting-check-on-startup" class="checkbox" bind:checked={checkOnStartup} />
          <span>起動時にアップデート確認 (checkOnStartup)</span>
        </label>

        <label class="flex cursor-pointer items-center gap-2 text-sm text-surface-700-300">
          <input type="checkbox" id="global-setting-prerelease" class="checkbox" bind:checked={prerelease} />
          <span>プレリリース版を含める (includePreReleases)</span>
        </label>

        <label class="flex cursor-pointer items-center gap-2 text-sm text-surface-700-300">
          <input type="checkbox" id="global-setting-allow-source-change" class="checkbox" bind:checked={allowSourceChange} />
          <span>ソース元の変更を許可 (allowSourceChange)</span>
        </label>

        <label class="flex cursor-pointer items-center gap-2 text-sm text-surface-700-300">
          <input type="checkbox" id="global-setting-restrict-notification" class="checkbox" bind:checked={restrictNotification} />
          <span>バックグラウンド制限警告を表示 (backgroundRestrictedNotification)</span>
        </label>
      </div>

      <div class="flex justify-end">
        <button type="submit" class="btn preset-filled-primary-500" disabled={savingSettings}>
          <span>{savingSettings ? '保存中...' : 'グローバル設定を保存'}</span>
        </button>
      </div>
    </form>
  </div>
</section>

<section class="dashboard-system-section mt-8">
  <div class="card bg-surface-100-900 border border-surface-200-800 p-6 backdrop-blur">
    <h3 class="label-text mb-3 uppercase tracking-wide text-surface-700-300">システムバックアップ / リストア</h3>
    <p class="mb-4 text-sm text-surface-600-400">データベースのレコードおよびアップロードされた APK ファイルを一括してバックアップ・復元します。</p>

    <div class="flex flex-wrap items-center gap-4">
      <a href="/api/backup" id="download-backup-btn" class="btn preset-tonal-primary-500" onclick={onDownloadBackup}>
        <span>📤 バックアップをダウンロード</span>
      </a>

      <div class="flex flex-wrap items-center gap-2 border-l border-surface-200-800 pl-4">
        <select id="restore-strategy" class="select w-auto" bind:value={restoreStrategy}>
          <option value="overwrite">上書き復元 (Overwrite)</option>
          <option value="merge">マージ復元 (Merge)</option>
        </select>
        <button id="restore-btn" class="btn preset-tonal-secondary-500" disabled={restoreBusy} onclick={onRestoreClick}>
          <span>{restoreBusy ? 'リストア中...' : '📥 バックアップからリストア'}</span>
        </button>
        <input type="file" id="restore-file-input" accept=".tar.gz" class="hidden" bind:this={restoreFileInput} onchange={onRestoreChange} />
      </div>
    </div>
  </div>
</section>

<AppModal active={appModalActive} appId={appModalId} />
<CategoryModal active={categoryModalActive} categoryName={categoryModalName} />
