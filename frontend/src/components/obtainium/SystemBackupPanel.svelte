<script lang="ts">
  import { Combobox, useListCollection } from '@skeletonlabs/skeleton-svelte';
  import { restoreBackup } from '../../api/api.js';
  import { showCustomToast } from '../../lib/toast.ts';
  import { confirmDialog } from '../../lib/dialogs.svelte.ts';

  let restoreFileInput = $state<HTMLInputElement | null>(null);
  let restoreStrategy = $state('overwrite');
  let restoreBusy = $state(false);

  const strategyOptions = [
    { label: '上書き復元 (Overwrite)', value: 'overwrite' },
    { label: 'マージ復元 (Merge)', value: 'merge' },
  ];
  const strategyCollection = useListCollection({
    items: strategyOptions,
    itemToString: (item) => item.label,
    itemToValue: (item) => item.value,
  });

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
      const { getToken } = await import('../../api/control_api.js');
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
</script>

<section class="dashboard-system-section mt-8">
  <div class="card bg-surface-100-900 border border-surface-200-800 p-6 backdrop-blur">
    <h3 class="label-text mb-3 uppercase tracking-wide text-surface-700-300">
      システムバックアップ / リストア
    </h3>
    <p class="mb-4 text-sm text-surface-600-400">
      データベースのレコードおよびアップロードされた APK ファイルを一括してバックアップ・復元します。
    </p>

    <div class="flex flex-wrap items-center gap-4">
      <a
        href="/api/backup"
        id="download-backup-btn"
        class="btn preset-tonal-primary-500"
        onclick={onDownloadBackup}
      >
        <span>📤 バックアップをダウンロード</span>
      </a>

      <div class="flex flex-wrap items-center gap-2 border-l border-surface-200-800 pl-4">
        <div class="w-auto min-w-[200px]">
          <Combobox
            openOnClick
            collection={strategyCollection}
            value={[restoreStrategy]}
            onValueChange={(details) => {
              restoreStrategy = details.value[0] ?? 'overwrite';
            }}
          >
            <Combobox.Control>
              <Combobox.Input id="restore-strategy" class="input" readonly />
              <Combobox.Trigger data-testid="restore-strategy-trigger" />
            </Combobox.Control>
            <Combobox.Positioner>
              <Combobox.Content class="z-50">
                {#each strategyOptions as item (item.value)}
                  <Combobox.Item {item} data-testid={`restore-strategy-option-${item.value}`}>
                    <Combobox.ItemText>{item.label}</Combobox.ItemText>
                    <Combobox.ItemIndicator />
                  </Combobox.Item>
                {/each}
              </Combobox.Content>
            </Combobox.Positioner>
          </Combobox>
        </div>
        <button
          id="restore-btn"
          class="btn preset-tonal-secondary-500"
          disabled={restoreBusy}
          onclick={onRestoreClick}
        >
          <span>{restoreBusy ? 'リストア中...' : '📥 バックアップからリストア'}</span>
        </button>
        <input
          type="file"
          id="restore-file-input"
          accept=".tar.gz"
          class="hidden"
          bind:this={restoreFileInput}
          onchange={onRestoreChange}
        />
      </div>
    </div>
  </div>
</section>
