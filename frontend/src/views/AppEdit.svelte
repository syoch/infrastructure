<script lang="ts">
  import { store, loadAllData } from '../lib/store.svelte.ts';
  import { goto as navigate } from '$app/navigation';
  import AppModal from '../components/AppModal.svelte';
  import CategoryModal from '../components/CategoryModal.svelte';
  import { FileUpload } from '@skeletonlabs/skeleton-svelte';
  import {
    saveApp,
    deleteApp,
    uploadLocalAPK,
    deleteLocalAPK,
    type App,
    type SaveAppPayload,
  } from '../api/api.js';
  import { validateUrlSourceMatch, detectSourceFromUrl } from '../lib/ui.js';
  import { showCustomToast } from '../lib/toast.ts';
  import { confirmDialog } from '../lib/dialogs.svelte.ts';

  let { id = '' }: { id?: string } = $props();

  const app = $derived(store.dashboardApps.find((a) => a.id === id) ?? null);
  const categories = $derived(Object.keys(store.settings.categories || {}));
  const apks = $derived(app?.apks || []);

  let appUrl = $state('');
  let appSource = $state('');
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

  let apkFile = $state<File | null>(null);
  let apkVersion = $state('');
  let apkArchitecture = $state('none');
  let apkUploading = $state(false);
  let apkUploadKey = $state(0);

  const VERSION_RE = /v?(\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?)/i;

  const isSelfHosted = $derived(appSource === 'HTML');

  $effect(() => {
    const found = store.dashboardApps.find((a) => a.id === id);
    if (found && populatedId !== found.id) {
      populatedId = found.id;
      populate(found);
    } else if (!found && populatedId === null && id && store.dashboardApps.length > 0) {
      navigate('/list');
    }
  });

  function resetUpload(): void {
    apkFile = null;
    apkUploadKey += 1;
  }

  function populate(a: App): void {
    appUrl = a.url || '';
    appSource = a.overrideSource || '';
    if (appSource === 'HTML') {
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
    apkVersion = a.apks && a.apks.length > 0 ? a.apks[a.apks.length - 1].version : '';
    apkArchitecture = 'none';
    saveConfirmPending = false;
    resetUpload();
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
    if (!app) return;
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
    if (!app) return;
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

  function updateFileDisplay(file: File): void {
    apkFile = file;
    const match = file.name.match(VERSION_RE);
    if (match && !apkVersion) apkVersion = match[1];
    if (file.name.includes('arm64-v8a')) apkArchitecture = 'arm64-v8a';
    else if (file.name.includes('armeabi-v7a')) apkArchitecture = 'armeabi-v7a';
    else if (file.name.includes('x86_64')) apkArchitecture = 'x86_64';
    else if (file.name.includes('x86')) apkArchitecture = 'x86';
    else if (file.name.includes('universal')) apkArchitecture = 'universal';
  }

  function onApkFileChange(details: { acceptedFiles: File[] }): void {
    const file = details.acceptedFiles[0];
    if (file) updateFileDisplay(file);
    else apkFile = null;
  }

  function onApkFileReject(): void {
    showCustomToast('APK ファイルのみアップロード可能です。', 'error');
  }

  async function onUpload(): Promise<void> {
    if (!app) return;
    if (!apkFile) {
      showCustomToast('アップロードする APK ファイルを選択してください。', 'error');
      return;
    }
    const version = apkVersion.trim();
    if (!version) {
      showCustomToast('バージョンを入力してください。', 'error');
      return;
    }
    const formData = new FormData();
    formData.append('app_id', app.id);
    formData.append('version', version);
    formData.append('architecture', apkArchitecture);
    formData.append('file', apkFile);
    apkUploading = true;
    try {
      showCustomToast('APK のアップロードを開始しました...', 'info');
      await uploadLocalAPK(formData);
      showCustomToast('APK を正常にアップロード・登録しました。', 'success');
      resetUpload();
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast(err instanceof Error ? err.message : 'APK のアップロードに失敗しました。', 'error');
    } finally {
      apkUploading = false;
    }
  }

  async function onDeleteApk(apkId: number): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'APK を削除',
      message: 'この APK を削除しますか？',
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteLocalAPK(String(apkId));
      showCustomToast('APK を削除しました。', 'success');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast(err instanceof Error ? err.message : 'APK の削除に失敗しました。', 'error');
    }
  }
</script>

<section class="dashboard-header-section mb-6">
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <h1 id="edit-view-title" class="h2">アプリ詳細設定</h1>
      <p class="mt-1 text-sm text-surface-700-300">アプリの詳細なスクレイピング条件やインストール時の挙動をカスタマイズします。</p>
    </div>
    <button id="edit-back-btn" class="btn preset-tonal" onclick={() => navigate('/list')}>
      <span>← 一覧に戻る</span>
    </button>
  </div>
</section>

<div class="card mx-auto max-w-3xl bg-surface-100-900 border border-surface-200-800 p-8 backdrop-blur">
  <form id="detailed-app-form" onsubmit={onSubmit}>
    <input type="hidden" id="edit-app-id-hidden" value={app?.id ?? ''} />

    <div class="flex flex-wrap gap-4">
      <div class="min-w-[200px] flex-1">
        <label for="edit-app-name" class="label-text mb-1.5">アプリ名</label>
        <input type="text" id="edit-app-name" class="input opacity-70" readonly value={app?.name ?? ''} />
      </div>
      <div class="min-w-[200px] flex-1">
        <label for="edit-app-id" class="label-text mb-1.5">パッケージID</label>
        <input type="text" id="edit-app-id" class="input opacity-70" readonly value={app?.id ?? ''} />
      </div>
    </div>

    <div class="mt-4">
      <label for="edit-app-url" class="label-text mb-1.5">ソースURL (GitHub / スクラップ対象) <span class="text-error-500">*</span></label>
      <input type="text" id="edit-app-url" class="input" required disabled={urlDisabled} bind:value={appUrl} />
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
        <div id="source-recommendation" class="mt-1.5 text-xs {recommendation ? 'block' : 'hidden'}">{recommendation}</div>
      </div>
      <div class="min-w-[200px] flex-1">
        <span class="label-text mb-1.5">カテゴリの選択</span>
        <div id="detailed-categories-checkboxes" class="mb-2 flex max-h-[120px] flex-col gap-1.5 overflow-y-auto rounded-container border border-surface-200-800 bg-surface-950/20 p-2">
          {#if categories.length === 0}
            <div class="py-1 text-xs text-surface-600-400">登録済みのカテゴリがありません。</div>
          {:else}
            {#each categories as cat (cat)}
              <label class="flex cursor-pointer items-center gap-2 text-sm">
                <input type="checkbox" name="app-category-checkbox" value={cat} class="checkbox" bind:checked={checked[cat]} />
                <span>{cat}</span>
              </label>
            {/each}
          {/if}
        </div>
        <input type="text" id="edit-app-categories" class="input field-sm" placeholder="新規追加（カンマ区切り）" bind:value={customCategories} />
      </div>
    </div>

    <div class="mt-6">
      <span class="label-text mb-3 font-semibold">追加設定 (Additional Settings)</span>
      <div class="flex flex-col gap-3.5">
        <label class="flex cursor-pointer flex-col items-start gap-1">
          <div class="flex items-center gap-2.5">
            <input type="checkbox" id="edit-setting-prerelease" class="checkbox" bind:checked={settingPrerelease} /> プレリリース版を含める (includePrereleases)
          </div>
          <span class="ml-7 text-xs leading-snug text-surface-600-400">GitHub等でプレリリースとしてマークされているバージョンもインストール対象にします。</span>
        </label>
        <label class="flex cursor-pointer flex-col items-start gap-1">
          <div class="flex items-center gap-2.5">
            <input type="checkbox" id="edit-setting-fallback" class="checkbox" bind:checked={settingFallback} /> 過去リリースへフォールバック (fallbackToOlderReleases)
          </div>
          <span class="ml-7 text-xs leading-snug text-surface-600-400">最新リリースの解析に失敗した場合、以前のバージョンへのフォールバックを許容します。</span>
        </label>
        <label class="flex cursor-pointer flex-col items-start gap-1">
          <div class="flex items-center gap-2.5">
            <input type="checkbox" id="edit-setting-version-detect" class="checkbox" bind:checked={settingVersionDetect} /> バージョン検出を有効化 (versionDetection)
          </div>
          <span class="ml-7 text-xs leading-snug text-surface-600-400">アップデート通知のためのバージョン比較ロジックを有効にします。</span>
        </label>
      </div>
    </div>

    <div class="mt-5">
      <span class="text-sm font-medium">APK フィルタ (apkFilterRegEx / invertAPKFilter)</span>
      <div class="mt-1.5 flex items-center gap-3">
        <input type="text" id="edit-setting-apk-filter" class="input field-sm flex-1" placeholder="正規表現パターン (例: .*arm64.*\.apk)" bind:value={settingApkFilter} />
        <label class="flex cursor-pointer items-center gap-1.5 whitespace-nowrap">
          <input type="checkbox" id="edit-setting-invert-filter" class="checkbox" bind:checked={settingInvertFilter} /> 反転 (invert)
        </label>
      </div>
      <span class="mt-1 block text-xs text-surface-600-400">正規表現に一致する APK のみダウンロードします。「反転」を有効にすると、一致する APK を除外します。</span>
    </div>

    <div class="mt-9 flex gap-3">
      <button type="submit" class="btn preset-filled-primary-500 flex-[2]">詳細設定を保存する</button>
      <button type="button" id="edit-delete-btn" class="btn preset-tonal-error flex-1" onclick={onDelete}>アプリを削除</button>
    </div>
  </form>
</div>

<div id="self-hosted-apk-card" class="card mx-auto mt-8 max-w-3xl bg-surface-100-900 border border-surface-200-800 p-8 backdrop-blur {isSelfHosted ? '' : 'hidden'}">
  <h2 class="h4">セルフホスト APK 管理 (Self-Hosted APKs)</h2>
  <p class="mt-1 text-sm text-surface-600-400">このアプリに関連付けられているセルフホスト APK ファイルを管理します。</p>

  <div class="mt-4">
    <span class="label-text mb-1.5">APK ファイルのアップロード</span>
    {#key apkUploadKey}
      <FileUpload
        accept={{ 'application/vnd.android.package-archive': ['.apk'] }}
        maxFiles={1}
        onFileChange={onApkFileChange}
        onFileReject={onApkFileReject}
      >
        <FileUpload.Dropzone class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-container border-2 border-dashed border-surface-300-700 bg-surface-100-900 p-8 text-center transition-colors hover:bg-surface-200-800 data-[dragging]:border-primary-500 data-[dragging]:bg-primary-500/10">
          <span class="text-3xl">📥</span>
          <span class="text-sm text-surface-700-300" id="apk-dropzone-text">
            {#if apkFile}
              選択されたファイル: <span class="break-all font-semibold text-success-500">{apkFile.name}</span> ({(apkFile.size / (1024 * 1024)).toFixed(2)} MB)
            {:else}
              ここに APK ファイルをドラッグ＆ドロップするか、クリックしてファイルを選択
            {/if}
          </span>
        </FileUpload.Dropzone>
        <FileUpload.HiddenInput id="apk-file-input" />
      </FileUpload>
    {/key}
  </div>

  <div class="mt-4 flex flex-wrap gap-4">
    <div class="min-w-[200px] flex-1">
      <label for="apk-version-input" class="label-text mb-1.5">バージョン <span class="text-error-500">*</span></label>
      <input type="text" id="apk-version-input" class="input" placeholder="e.g. 1.18.0" bind:value={apkVersion} />
    </div>
    <div class="min-w-[200px] flex-1">
      <label for="apk-arch-select" class="label-text mb-1.5">アーキテクチャ</label>
      <select id="apk-arch-select" class="select" bind:value={apkArchitecture}>
        <option value="none">指定なし / 自動 (none/auto)</option>
        <option value="universal">universal</option>
        <option value="arm64-v8a">arm64-v8a</option>
        <option value="armeabi-v7a">armeabi-v7a</option>
        <option value="x86_64">x86_64</option>
        <option value="x86">x86</option>
      </select>
    </div>
  </div>

  <div class="mt-4">
    <button type="button" id="apk-upload-btn" class="btn preset-filled-primary-500 w-full" disabled={apkUploading} onclick={onUpload}>
      {apkUploading ? 'アップロード中...' : 'APK をアップロードして登録する'}
    </button>
  </div>

  <hr class="my-6 border-surface-200-800" />

  <h3 class="h5 mb-3">登録済み APK 一覧</h3>
  <div class="overflow-x-auto">
    <table class="table mt-4 text-sm">
      <thead>
        <tr>
          <th>バージョン</th>
          <th>アーキテクチャ</th>
          <th>ファイルハッシュ (SHA-256)</th>
          <th class="w-20 text-right">操作</th>
        </tr>
      </thead>
      <tbody id="apk-list-tbody">
        {#if apks.length === 0}
          <tr>
            <td colspan="4" class="p-4 text-center text-surface-600-400">登録されているセルフホスト APK がありません。</td>
          </tr>
        {:else}
          {#each apks as apk (apk.id)}
            <tr>
              <td>{apk.version}</td>
              <td>{apk.architecture || '指定なし/自動'}</td>
              <td class="font-mono text-xs text-surface-600-400" title={apk.file_hash}>{apk.file_hash.substring(0, 16)}...</td>
              <td class="text-right">
                <button class="btn preset-tonal-error [--btn-size:var(--text-sm)]" data-testid="apk-delete-btn" onclick={() => onDeleteApk(apk.id)}>削除</button>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</div>

<AppModal active={false} appId={null} />
<CategoryModal active={false} categoryName={null} />
