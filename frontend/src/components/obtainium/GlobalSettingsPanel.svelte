<script lang="ts">
  import { store, loadAllData } from '../../lib/store.svelte.ts';
  import { saveSettings } from '../../api/api.js';
  import { showCustomToast } from '../../lib/toast.ts';

  let theme = $state('system');
  let checkInterval = $state<string | number>('');
  let checkOnStartup = $state(false);
  let prerelease = $state(false);
  let allowSourceChange = $state(false);
  let restrictNotification = $state(false);
  let savingSettings = $state(false);

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

<section class="dashboard-settings-section mt-8">
  <div class="card bg-surface-100-900 border border-surface-200-800 p-6 backdrop-blur">
    <h3 class="label-text mb-3 uppercase tracking-wide text-surface-700-300">
      Obtainium グローバル設定 (Global Settings)
    </h3>
    <p class="mb-5 text-sm text-surface-600-400">
      Obtainium アプリ全体の共通動作や表示テーマなどの設定を管理します。
    </p>

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
          <label for="global-setting-check-interval" class="label-text mb-1.5"
            >アップデートチェック間隔 (checkInterval / 時間)</label
          >
          <input
            type="number"
            id="global-setting-check-interval"
            class="input"
            min="0"
            placeholder="例: 24"
            bind:value={checkInterval}
          />
        </div>
      </div>

      <div
        class="mb-6 grid gap-4"
        style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr));"
      >
        <label class="flex cursor-pointer items-center gap-2 text-sm text-surface-700-300">
          <input
            type="checkbox"
            id="global-setting-check-on-startup"
            class="checkbox"
            bind:checked={checkOnStartup}
          />
          <span>起動時にアップデート確認 (checkOnStartup)</span>
        </label>

        <label class="flex cursor-pointer items-center gap-2 text-sm text-surface-700-300">
          <input
            type="checkbox"
            id="global-setting-prerelease"
            class="checkbox"
            bind:checked={prerelease}
          />
          <span>プレリリース版を含める (includePreReleases)</span>
        </label>

        <label class="flex cursor-pointer items-center gap-2 text-sm text-surface-700-300">
          <input
            type="checkbox"
            id="global-setting-allow-source-change"
            class="checkbox"
            bind:checked={allowSourceChange}
          />
          <span>ソース元の変更を許可 (allowSourceChange)</span>
        </label>

        <label class="flex cursor-pointer items-center gap-2 text-sm text-surface-700-300">
          <input
            type="checkbox"
            id="global-setting-restrict-notification"
            class="checkbox"
            bind:checked={restrictNotification}
          />
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
