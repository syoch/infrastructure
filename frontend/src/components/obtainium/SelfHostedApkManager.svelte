<script lang="ts">
  import { FileUpload } from '@skeletonlabs/skeleton-svelte';
  import { loadAllData } from '../../lib/store.svelte.ts';
  import { uploadLocalAPK, deleteLocalAPK, type App } from '../../api/api.js';
  import { showCustomToast } from '../../lib/toast.ts';
  import { confirmDialog } from '../../lib/dialogs.svelte.ts';

  let { app, isSelfHosted }: { app: App; isSelfHosted: boolean } = $props();

  const apks = $derived(app.apks || []);

  let apkFile = $state<File | null>(null);
  let apkVersion = $state('');
  let apkArchitecture = $state('none');
  let apkUploading = $state(false);
  let apkUploadKey = $state(0);
  let populatedId: string | null = null;

  const VERSION_RE = /v?(\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?)/i;

  $effect(() => {
    if (populatedId !== app.id) {
      populatedId = app.id;
      apkVersion = app.apks && app.apks.length > 0 ? app.apks[app.apks.length - 1].version : '';
      apkArchitecture = 'none';
      resetUpload();
    }
  });

  function resetUpload(): void {
    apkFile = null;
    apkUploadKey += 1;
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
      showCustomToast(
        err instanceof Error ? err.message : 'APK のアップロードに失敗しました。',
        'error'
      );
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

<div
  id="self-hosted-apk-card"
  class="card mx-auto mt-8 max-w-3xl bg-surface-100-900 border border-surface-200-800 p-8 backdrop-blur {isSelfHosted
    ? ''
    : 'hidden'}"
>
  <h2 class="h4">セルフホスト APK 管理 (Self-Hosted APKs)</h2>
  <p class="mt-1 text-sm text-surface-600-400">
    このアプリに関連付けられているセルフホスト APK ファイルを管理します。
  </p>

  <div class="mt-4">
    <span class="label-text mb-1.5">APK ファイルのアップロード</span>
    {#key apkUploadKey}
      <FileUpload
        accept={{ 'application/vnd.android.package-archive': ['.apk'] }}
        maxFiles={1}
        onFileChange={onApkFileChange}
        onFileReject={onApkFileReject}
      >
        <FileUpload.Dropzone
          class="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-container border-2 border-dashed border-surface-300-700 bg-surface-100-900 p-8 text-center transition-colors hover:bg-surface-200-800 data-[dragging]:border-primary-500 data-[dragging]:bg-primary-500/10"
        >
          <span class="text-3xl">📥</span>
          <span class="text-sm text-surface-700-300" id="apk-dropzone-text">
            {#if apkFile}
              選択されたファイル: <span class="break-all font-semibold text-success-500"
                >{apkFile.name}</span
              > ({(apkFile.size / (1024 * 1024)).toFixed(2)} MB)
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
      <label for="apk-version-input" class="label-text mb-1.5"
        >バージョン <span class="text-error-500">*</span></label
      >
      <input
        type="text"
        id="apk-version-input"
        class="input"
        placeholder="e.g. 1.18.0"
        bind:value={apkVersion}
      />
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
    <button
      type="button"
      id="apk-upload-btn"
      class="btn preset-filled-primary-500 w-full"
      disabled={apkUploading}
      onclick={onUpload}
    >
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
            <td colspan="4" class="p-4 text-center text-surface-600-400">
              登録されているセルフホスト APK がありません。
            </td>
          </tr>
        {:else}
          {#each apks as apk (apk.id)}
            <tr>
              <td>{apk.version}</td>
              <td>{apk.architecture || '指定なし/自動'}</td>
              <td class="font-mono text-xs text-surface-600-400" title={apk.file_hash}
                >{apk.file_hash.substring(0, 16)}...</td
              >
              <td class="text-right">
                <button
                  class="btn preset-tonal-error [--btn-size:var(--text-sm)]"
                  data-testid="apk-delete-btn"
                  onclick={() => onDeleteApk(apk.id)}>削除</button
                >
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</div>
