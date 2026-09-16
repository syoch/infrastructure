<script lang="ts">
  import { store, loadAllData } from '../lib/store.svelte.ts';
  import { navigate } from '../lib/router.svelte.ts';
  import AppModal from '../components/AppModal.svelte';
  import CategoryModal from '../components/CategoryModal.svelte';
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
  let apkFileInput = $state<HTMLInputElement | null>(null);
  let dropzone = $state<HTMLDivElement | null>(null);

  const VERSION_RE = /v?(\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?)/i;

  $effect(() => {
    const found = store.dashboardApps.find((a) => a.id === id);
    if (found && populatedId !== found.id) {
      populatedId = found.id;
      populate(found);
    } else if (!found && populatedId === null && id && store.dashboardApps.length > 0) {
      navigate('#list');
    }
  });

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
    apkFile = null;
    apkVersion = a.apks && a.apks.length > 0 ? a.apks[a.apks.length - 1].version : '';
    apkArchitecture = 'none';
    saveConfirmPending = false;
    if (apkFileInput) apkFileInput.value = '';
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

  const selfHostedStyle = $derived(
    appSource === 'HTML'
      ? 'max-width:800px;margin:24px auto 0 auto;background:var(--bg-surface);border:1px solid var(--border-color);border-radius:var(--radius-lg);padding:32px;backdrop-filter:blur(20px);display:block;'
      : 'display:none;'
  );

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
      navigate('#list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      alert('詳細設定の保存に失敗しました。');
    }
  }

  async function onDelete(): Promise<void> {
    if (!app) return;
    if (!confirm(`アプリ '${app.id}' を削除してもよろしいですか？`)) return;
    try {
      await deleteApp(app.id);
      navigate('#list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      alert('アプリの削除に失敗しました。');
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

  function onFileInputChange(e: Event): void {
    const input = e.currentTarget as HTMLInputElement;
    if (input.files && input.files.length > 0) updateFileDisplay(input.files[0]);
  }

  function onDragOver(e: DragEvent): void {
    e.preventDefault();
    dropzone?.classList.add('dragover');
  }

  function onDragLeave(): void {
    dropzone?.classList.remove('dragover');
  }

  function onDrop(e: DragEvent): void {
    e.preventDefault();
    dropzone?.classList.remove('dragover');
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.name.endsWith('.apk')) {
        if (apkFileInput) apkFileInput.files = files;
        updateFileDisplay(file);
      } else {
        showCustomToast('APK ファイルのみアップロード可能です。', 'error');
      }
    }
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
      apkFile = null;
      if (apkFileInput) apkFileInput.value = '';
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast(err instanceof Error ? err.message : 'APK のアップロードに失敗しました。', 'error');
    } finally {
      apkUploading = false;
    }
  }

  async function onDeleteApk(apkId: number): Promise<void> {
    if (!confirm('この APK を削除しますか？')) return;
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

<section class="dashboard-header-section">
  <div class="dashboard-title-row">
    <div>
      <h1 id="edit-view-title">アプリ詳細設定</h1>
      <p class="hero-subtitle" style="margin:4px 0 0 0;text-align:left;">アプリの詳細なスクレイピング条件やインストール時の挙動をカスタマイズします。</p>
    </div>
    <button id="edit-back-btn" class="btn btn-secondary" onclick={() => navigate('#list')}>
      <span>← 一覧に戻る</span>
    </button>
  </div>
</section>

<div class="dashboard-card" style="max-width:800px;margin:0 auto;background:var(--bg-surface);border:1px solid var(--border-color);border-radius:var(--radius-lg);padding:32px;backdrop-filter:blur(20px);">
  <form id="detailed-app-form" onsubmit={onSubmit}>
    <input type="hidden" id="edit-app-id-hidden" value={app?.id ?? ''} />

    <div class="form-row">
      <div class="form-group col-6">
        <label for="edit-app-name">アプリ名</label>
        <input type="text" id="edit-app-name" readonly value={app?.name ?? ''} style="background:rgba(255,255,255,0.02);color:var(--color-text-secondary);" />
      </div>
      <div class="form-group col-6">
        <label for="edit-app-id">パッケージID</label>
        <input type="text" id="edit-app-id" readonly value={app?.id ?? ''} style="background:rgba(255,255,255,0.02);color:var(--color-text-secondary);" />
      </div>
    </div>

    <div class="form-group">
      <label for="edit-app-url">ソースURL (GitHub / スクラップ対象) <span class="required">*</span></label>
      <input type="text" id="edit-app-url" required disabled={urlDisabled} bind:value={appUrl} />
    </div>

    <div class="form-row">
      <div class="form-group col-6">
        <label for="edit-app-source">ソース元タイプ</label>
        <select id="edit-app-source" value={appSource} onchange={onSourceChange}>
          <option value="">Auto-detect (推奨)</option>
          <option value="GitHub">GitHub</option>
          <option value="HTML">HTML (Self-Hosted / WebScrape)</option>
          <option value="F-Droid">F-Droid</option>
          <option value="GitLab">GitLab</option>
          <option value="APKPure">APKPure</option>
        </select>
        <div id="source-recommendation" class="source-recommendation" style={recommendation ? 'display:block;' : 'display:none;'}>{recommendation}</div>
      </div>
      <div class="form-group col-6">
        <span class="form-label">カテゴリの選択</span>
        <div id="detailed-categories-checkboxes" style="display:flex;flex-direction:column;gap:6px;max-height:120px;overflow-y:auto;background:rgba(0,0,0,0.15);padding:8px 12px;border-radius:var(--radius-sm);border:1px solid var(--border-color);margin-bottom:8px;">
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
        <input type="text" id="edit-app-categories" placeholder="新規追加（カンマ区切り）" style="font-size:0.85rem;padding:6px 10px;" bind:value={customCategories} />
      </div>
    </div>

    <div class="form-group" style="margin-top:24px;">
      <span class="form-label" style="margin-bottom:12px;display:block;font-weight:600;">追加設定 (Additional Settings)</span>
      <div class="checkbox-group">
        <label class="checkbox-label" style="display:flex;flex-direction:column;align-items:flex-start;gap:4px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <input type="checkbox" id="edit-setting-prerelease" bind:checked={settingPrerelease} /> プレリリース版を含める (includePrereleases)
          </div>
          <span style="font-size:0.75rem;color:var(--color-text-muted);margin-left:26px;line-height:1.4;">GitHub等でプレリリースとしてマークされているバージョンもインストール対象にします。</span>
        </label>
        <label class="checkbox-label" style="display:flex;flex-direction:column;align-items:flex-start;gap:4px;margin-top:14px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <input type="checkbox" id="edit-setting-fallback" bind:checked={settingFallback} /> 過去リリースへフォールバック (fallbackToOlderReleases)
          </div>
          <span style="font-size:0.75rem;color:var(--color-text-muted);margin-left:26px;line-height:1.4;">最新リリースの解析に失敗した場合、以前のバージョンへのフォールバックを許容します。</span>
        </label>
        <label class="checkbox-label" style="display:flex;flex-direction:column;align-items:flex-start;gap:4px;margin-top:14px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <input type="checkbox" id="edit-setting-version-detect" bind:checked={settingVersionDetect} /> バージョン検出を有効化 (versionDetection)
          </div>
          <span style="font-size:0.75rem;color:var(--color-text-muted);margin-left:26px;line-height:1.4;">アップデート通知のためのバージョン比較ロジックを有効にします。</span>
        </label>
      </div>
    </div>

    <div class="form-row" style="margin-top:20px;">
      <div class="form-group col-12">
        <span style="font-size:0.9rem;font-weight:500;">APK フィルタ (apkFilterRegEx / invertAPKFilter)</span>
        <div style="display:flex;gap:12px;align-items:center;margin-top:6px;">
          <input type="text" id="edit-setting-apk-filter" placeholder="正規表現パターン (例: .*arm64.*\.apk)" style="flex:1;font-size:0.85rem;padding:6px 10px;background:rgba(0,0,0,0.15);border:1px solid var(--border-color);border-radius:var(--radius-sm);color:var(--color-text);" bind:value={settingApkFilter} />
          <label class="checkbox-label" style="display:flex;align-items:center;gap:6px;margin:0;white-space:nowrap;">
            <input type="checkbox" id="edit-setting-invert-filter" bind:checked={settingInvertFilter} /> 反転 (invert)
          </label>
        </div>
        <span style="font-size:0.75rem;color:var(--color-text-muted);margin-top:4px;display:block;">正規表現に一致する APK のみダウンロードします。「反転」を有効にすると、一致する APK を除外します。</span>
      </div>
    </div>

    <div class="form-actions" style="margin-top:36px;">
      <button type="submit" class="btn btn-primary" style="flex:2;">詳細設定を保存する</button>
      <button type="button" id="edit-delete-btn" class="btn btn-secondary" style="color:#ff5252;border-color:rgba(255,82,82,0.2);flex:1;" onclick={onDelete}>アプリを削除</button>
    </div>
  </form>
</div>

<div id="self-hosted-apk-card" class="dashboard-card apk-management-card" style={selfHostedStyle}>
  <h2 class="card-title">セルフホスト APK 管理 (Self-Hosted APKs)</h2>
  <p class="card-subtitle">このアプリに関連付けられているセルフホスト APK ファイルを管理します。</p>

  <div class="form-group">
    <span class="form-label">APK ファイルのアップロード</span>
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="upload-dropzone"
      id="apk-dropzone"
      bind:this={dropzone}
      ondragover={onDragOver}
      ondragleave={onDragLeave}
      ondrop={onDrop}
    >
      <span class="upload-dropzone-icon">📥</span>
      <span class="upload-dropzone-text" id="apk-dropzone-text">
        {#if apkFile}
          選択されたファイル: <span class="upload-dropzone-filename">{apkFile.name}</span> ({(apkFile.size / (1024 * 1024)).toFixed(2)} MB)
        {:else}
          ここに APK ファイルをドラッグ＆ドロップするか、クリックしてファイルを選択
        {/if}
      </span>
      <input type="file" id="apk-file-input" accept=".apk" bind:this={apkFileInput} onchange={onFileInputChange} />
    </div>
  </div>

  <div class="form-row" style="margin-top:16px;">
    <div class="form-group col-6">
      <label for="apk-version-input">バージョン <span class="required">*</span></label>
      <input type="text" id="apk-version-input" placeholder="e.g. 1.18.0" bind:value={apkVersion} />
    </div>
    <div class="form-group col-6">
      <label for="apk-arch-select">アーキテクチャ</label>
      <select id="apk-arch-select" bind:value={apkArchitecture}>
        <option value="none">指定なし / 自動 (none/auto)</option>
        <option value="universal">universal</option>
        <option value="arm64-v8a">arm64-v8a</option>
        <option value="armeabi-v7a">armeabi-v7a</option>
        <option value="x86_64">x86_64</option>
        <option value="x86">x86</option>
      </select>
    </div>
  </div>

  <div style="margin-top:16px;">
    <button type="button" id="apk-upload-btn" class="btn btn-primary" style="width:100%;" disabled={apkUploading} onclick={onUpload}>
      {apkUploading ? 'アップロード中...' : 'APK をアップロードして登録する'}
    </button>
  </div>

  <hr style="border:0;border-top:1px solid var(--border-color);margin:32px 0 24px 0;" />

  <h3 style="font-size:1.1rem;font-weight:600;margin-bottom:12px;">登録済み APK 一覧</h3>
  <div style="overflow-x:auto;">
    <table class="apk-table">
      <thead>
        <tr>
          <th>バージョン</th>
          <th>アーキテクチャ</th>
          <th>ファイルハッシュ (SHA-256)</th>
          <th style="text-align:right;width:80px;">操作</th>
        </tr>
      </thead>
      <tbody id="apk-list-tbody">
        {#if apks.length === 0}
          <tr>
            <td colspan="4" style="text-align:center;color:var(--color-text-muted);padding:16px;">登録されているセルフホスト APK がありません。</td>
          </tr>
        {:else}
          {#each apks as apk (apk.id)}
            <tr>
              <td>{apk.version}</td>
              <td>{apk.architecture || '指定なし/自動'}</td>
              <td class="apk-hash-text" title={apk.file_hash}>{apk.file_hash.substring(0, 16)}...</td>
              <td style="text-align:right;">
                <button class="delete-apk-btn" onclick={() => onDeleteApk(apk.id)}>削除</button>
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
