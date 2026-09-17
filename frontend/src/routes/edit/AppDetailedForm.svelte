<script lang="ts">
  import { goto as navigate } from '$app/navigation';
  import { store, loadAllData } from '../../lib/store.svelte.ts';
  import { saveApp, deleteApp, type App, type SaveAppPayload } from '../../api/api.js';
  import { validateUrlSourceMatch, detectSourceFromUrl } from '../../lib/ui.js';
  import { showCustomToast } from '../../lib/toast.ts';
  import { confirmDialog } from '../../lib/dialogs.svelte.ts';

  let {
    app,
    appSource = $bindable(''),
  }: { app: App; appSource?: string } = $props();

  const categories = $derived(Object.keys(store.settings.categories || {}));

  let appUrl = $state('');
  let urlDisabled = $state(false);
  let customCategories = $state('');
  let checked = $state<Record<string, boolean>>({});
  let settingPrerelease = $state(false);
  let settingFallback = $state(true);
  let settingVersionDetect = $state(true);
  let settingApkFilter = $state('');
  let settingInvertFilter = $state(false);
  let saveConfirmPending = false;
  let populatedId: string | null = null;

  $effect(() => {
    if (populatedId !== app.id) {
      populatedId = app.id;
      populate(app);
    }
  });

  function populate(a: App): void {
    appUrl = a.url || '';
    const source = a.overrideSource || '';
    appSource = source;
    if (source === 'HTML') {
      appUrl = '/scrape-index.html';
      urlDisabled = true;
    } else {
      urlDisabled = false;
    }
    const next: Record<string, boolean> = {};
    (a.categories || []).forEach((c) => {
      next[c] = true;
    });
    checked = next;
    customCategories = '';
    const s = a.additionalSettings || {};
    settingPrerelease = s.includePrereleases || false;
    settingFallback = s.fallbackToOlderReleases !== false;
    settingVersionDetect = s.versionDetection !== false;
    settingApkFilter = s.apkFilterRegEx || '';
    settingInvertFilter = s.invertAPKFilter || false;
    saveConfirmPending = false;
  }

  const recommendation = $derived.by(() => {
    const url = appUrl.trim();
    if (!appSource) {
      const detected = detectSourceFromUrl(url);
      return detected ? `💡 この URL は ${detected} として自動検出されます` : '';
    }
    const { valid, warning } = validateUrlSourceMatch(url, appSource);
    return !valid && warning ? `⚠️ ${warning}` : '';
  });

  function onSourceChange(e: Event): void {
    appSource = (e.currentTarget as HTMLSelectElement).value;
    if (appSource === 'HTML') {
      appUrl = '/scrape-index.html';
      urlDisabled = true;
    } else {
      if (appUrl === '/scrape-index.html') appUrl = '';
      urlDisabled = false;
    }
  }

  async function onSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    const current = app;
    const selected = categories.filter((c) => checked[c]);
    const custom = customCategories
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
    const merged = Array.from(new Set([...selected, ...custom]));
    const payload: SaveAppPayload = {
      id: current.id,
      name: current.name,
      url: appUrl.trim(),
      overrideSource: appSource || undefined,
      categories: merged,
      additionalSettings: {
        ...(current.additionalSettings || {}),
        includePrereleases: settingPrerelease,
        fallbackToOlderReleases: settingFallback,
        versionDetection: settingVersionDetect,
        apkFilterRegEx: settingApkFilter,
        invertAPKFilter: settingInvertFilter,
      },
    };
    const { valid } = validateUrlSourceMatch(payload.url, payload.overrideSource);
    if (!valid && !saveConfirmPending) {
      saveConfirmPending = true;
      showCustomToast(
        '⚠️ URL とソース元の組み合わせに問題がある可能性があります。もう一度「保存」を押して確認してください。',
        'warning',
        5000
      );
      return;
    }
    saveConfirmPending = false;
    try {
      await saveApp(payload);
      navigate('/list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast('詳細設定の保存に失敗しました。', 'error');
    }
  }

  async function onDelete(): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'アプリを削除',
      message: `アプリ '${app.id}' を削除してもよろしいですか？`,
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteApp(app.id);
      navigate('/list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast('アプリの削除に失敗しました。', 'error');
    }
  }
</script>

<div class="card mx-auto max-w-3xl bg-surface-100-900 border border-surface-200-800 p-8 backdrop-blur">
  <form id="detailed-app-form" onsubmit={onSubmit}>
    <input type="hidden" id="edit-app-id-hidden" value={app.id} />

    <div class="flex flex-wrap gap-4">
      <div class="min-w-[200px] flex-1">
        <label for="edit-app-name" class="label-text mb-1.5">アプリ名</label>
        <input type="text" id="edit-app-name" class="input opacity-70" readonly value={app.name} />
      </div>
      <div class="min-w-[200px] flex-1">
        <label for="edit-app-id" class="label-text mb-1.5">パッケージID</label>
        <input type="text" id="edit-app-id" class="input opacity-70" readonly value={app.id} />
      </div>
    </div>

    <div class="mt-4">
      <label for="edit-app-url" class="label-text mb-1.5"
        >ソースURL (GitHub / スクラップ対象) <span class="text-error-500">*</span></label
      >
      <input
        type="text"
        id="edit-app-url"
        class="input"
        required
        disabled={urlDisabled}
        bind:value={appUrl}
      />
    </div>

    <div class="mt-4 flex flex-wrap gap-4">
      <div class="min-w-[200px] flex-1">
        <label for="edit-app-source" class="label-text mb-1.5">ソース元タイプ</label>
        <select id="edit-app-source" class="select" value={appSource} onchange={onSourceChange}>
          <option value="">Auto-detect (推奨)</option>
          <option value="GitHub">GitHub</option>
          <option value="HTML">HTML (Self-Hosted / WebScrape)</option>
          <option value="F-Droid">F-Droid</option>
          <option value="GitLab">GitLab</option>
          <option value="APKPure">APKPure</option>
        </select>
        <div
          id="source-recommendation"
          class="mt-1.5 text-xs {recommendation ? 'block' : 'hidden'}">{recommendation}</div
        >
      </div>
      <div class="min-w-[200px] flex-1">
        <span class="label-text mb-1.5">カテゴリの選択</span>
        <div
          id="detailed-categories-checkboxes"
          class="mb-2 flex max-h-[120px] flex-col gap-1.5 overflow-y-auto rounded-container border border-surface-200-800 bg-surface-950/20 p-2"
        >
          {#if categories.length === 0}
            <div class="py-1 text-xs text-surface-600-400">登録済みのカテゴリがありません。</div>
          {:else}
            {#each categories as cat (cat)}
              <label class="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  name="app-category-checkbox"
                  value={cat}
                  class="checkbox"
                  bind:checked={checked[cat]}
                />
                <span>{cat}</span>
              </label>
            {/each}
          {/if}
        </div>
        <input
          type="text"
          id="edit-app-categories"
          class="input field-sm"
          placeholder="新規追加（カンマ区切り）"
          bind:value={customCategories}
        />
      </div>
    </div>

    <div class="mt-6">
      <span class="label-text mb-3 font-semibold">追加設定 (Additional Settings)</span>
      <div class="flex flex-col gap-3.5">
        <label class="flex cursor-pointer flex-col items-start gap-1">
          <div class="flex items-center gap-2.5">
            <input
              type="checkbox"
              id="edit-setting-prerelease"
              class="checkbox"
              bind:checked={settingPrerelease}
            />
            プレリリース版を含める (includePrereleases)
          </div>
          <span class="ml-7 text-xs leading-snug text-surface-600-400"
            >GitHub等でプレリリースとしてマークされているバージョンもインストール対象にします。</span
          >
        </label>
        <label class="flex cursor-pointer flex-col items-start gap-1">
          <div class="flex items-center gap-2.5">
            <input
              type="checkbox"
              id="edit-setting-fallback"
              class="checkbox"
              bind:checked={settingFallback}
            />
            過去リリースへフォールバック (fallbackToOlderReleases)
          </div>
          <span class="ml-7 text-xs leading-snug text-surface-600-400"
            >最新リリースの解析に失敗した場合、以前のバージョンへのフォールバックを許容します。</span
          >
        </label>
        <label class="flex cursor-pointer flex-col items-start gap-1">
          <div class="flex items-center gap-2.5">
            <input
              type="checkbox"
              id="edit-setting-version-detect"
              class="checkbox"
              bind:checked={settingVersionDetect}
            />
            バージョン検出を有効化 (versionDetection)
          </div>
          <span class="ml-7 text-xs leading-snug text-surface-600-400"
            >アップデート通知のためのバージョン比較ロジックを有効にします。</span
          >
        </label>
      </div>
    </div>

    <div class="mt-5">
      <span class="text-sm font-medium">APK フィルタ (apkFilterRegEx / invertAPKFilter)</span>
      <div class="mt-1.5 flex items-center gap-3">
        <input
          type="text"
          id="edit-setting-apk-filter"
          class="input field-sm flex-1"
          placeholder="正規表現パターン (例: .*arm64.*\.apk)"
          bind:value={settingApkFilter}
        />
        <label class="flex cursor-pointer items-center gap-1.5 whitespace-nowrap">
          <input
            type="checkbox"
            id="edit-setting-invert-filter"
            class="checkbox"
            bind:checked={settingInvertFilter}
          />
          反転 (invert)
        </label>
      </div>
      <span class="mt-1 block text-xs text-surface-600-400"
        >正規表現に一致する APK のみダウンロードします。「反転」を有効にすると、一致する APK
        を除外します。</span
      >
    </div>

    <div class="mt-9 flex gap-3">
      <button type="submit" class="btn preset-filled-primary-500 flex-[2]">詳細設定を保存する</button>
      <button
        type="button"
        id="edit-delete-btn"
        class="btn preset-tonal-error flex-1"
        onclick={onDelete}>アプリを削除</button
      >
    </div>
  </form>
</div>
