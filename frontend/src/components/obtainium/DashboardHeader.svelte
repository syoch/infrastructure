<script lang="ts">
  import { goto as navigate } from '$app/navigation';
  import { compileSettings, importObtainiumConfig } from '../../api/api.js';
  import { loadAllData } from '../../lib/store.svelte.ts';
  import { showCustomToast, showToast } from '../../lib/toast.ts';

  let compileBtn = $state<HTMLButtonElement | null>(null);
  let importJsonFile = $state<HTMLInputElement | null>(null);
  let importBusy = $state(false);

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
</script>

<section class="dashboard-header-section mb-6">
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <h1 class="h2">アプリ管理ダッシュボード</h1>
      <p class="mt-1 text-sm text-surface-700-300">
        リポジトリ内のアプリ追加・編集・削除および設定のコンパイルを行います。
      </p>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <button
        id="import-json-btn"
        class="btn preset-tonal-primary-500"
        disabled={importBusy}
        onclick={onImportClick}
      >
        <span>{importBusy ? 'インポート中...' : '📥 JSONインポート'}</span>
      </button>
      <input
        type="file"
        id="import-json-file"
        accept=".json"
        class="hidden"
        bind:this={importJsonFile}
        onchange={onImportChange}
      />
      <button
        id="add-app-btn"
        class="btn preset-tonal-secondary-500"
        onclick={() => navigate('/new?type=app')}
      >
        <span>➕ 新規アプリ登録</span>
      </button>
      <button
        id="compile-btn"
        class="btn preset-filled-primary-500"
        bind:this={compileBtn}
        onclick={onCompile}
      >
        <span>設定をコンパイルして反映</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="size-4">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" fill="none" />
        </svg>
      </button>
    </div>
  </div>
</section>
