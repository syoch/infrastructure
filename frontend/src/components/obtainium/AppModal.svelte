<script lang="ts">
  import { store, loadAllData } from '../../lib/store.svelte.ts';
  import { goto as navigate } from '$app/navigation';
  import { Combobox, Dialog, Portal, useListCollection } from '@skeletonlabs/skeleton-svelte';
  import { saveApp, type SaveAppPayload, type App } from '../../api/api.js';
  import { showCustomToast } from '../../lib/toast.ts';

  let {
    active = false,
    appId = null,
  }: { active?: boolean; appId?: string | null } = $props();

  const sourceOptions = [
    { label: 'GitHub', value: 'GitHub' },
    { label: 'HTML (Self-Hosted / WebScrape)', value: 'HTML' },
    { label: 'F-Droid', value: 'F-Droid' },
    { label: 'GitLab', value: 'GitLab' },
  ];
  const sourceCollection = $derived(
    useListCollection({
      items: sourceOptions,
      itemToString: (item) => item.label,
      itemToValue: (item) => item.value,
    })
  );

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

  function close(): void {
    navigate('/list');
  }

  function onSourceChange(value: string): void {
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
      navigate('/list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast('保存に失敗しました。', 'error');
    }
  }

  function onDetail(): void {
    navigate(`/edit?type=app&id=${encodeURIComponent(pkgId)}`);
  }
</script>

<Dialog
  open={active}
  aria-label="アプリ編集"
  onOpenChange={(details) => {
    if (!details.open) close();
  }}
>
  <Portal>
    <Dialog.Backdrop class="fixed inset-0 z-[80] bg-surface-950/60" />
    <Dialog.Positioner class="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <Dialog.Content
        id="app-modal"
        data-testid="app-modal"
        class="card bg-surface-100-900 relative max-h-[90vh] w-full max-w-xl overflow-y-auto p-6 shadow-xl"
      >
        <button
          class="preset-tonal absolute top-3 right-3 h-4 w-4"
          id="app-modal-close"
          type="button"
          aria-label="閉じる"
          onclick={close}
        >
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            stroke="currentColor"
            stroke-width="2.5"
            fill="none"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        <Dialog.Title>
          {#snippet element(attributes)}
            <h2 {...attributes} id="app-modal-title" class="h4">
              {editMode ? 'アプリ簡易編集' : 'アプリを登録する'}
            </h2>
          {/snippet}
        </Dialog.Title>
        <p class="mt-1 text-sm text-surface-600-400" id="app-modal-subtitle">
          {editMode ? `パッケージ ID: ${pkgId}` : 'アプリの基本情報を入力してください。'}
        </p>

        <form id="quick-app-form" onsubmit={onSubmit} class="mt-4">
          <input type="hidden" id="quick-app-edit-mode" value={editMode ? 'true' : 'false'} />

          <div class="mb-4">
            <label for="quick-app-id" class="label-text mb-1.5">パッケージID (Package ID) <span class="text-error-500">*</span></label>
            <input
              type="text"
              id="quick-app-id"
              class="input"
              placeholder="e.g. com.termux"
              required
              disabled={editMode}
              bind:value={pkgId}
            />
          </div>

          <div class="mb-4">
            <label for="quick-app-name" class="label-text mb-1.5">アプリ名 (App Name) <span class="text-error-500">*</span></label>
            <input
              type="text"
              id="quick-app-name"
              class="input"
              placeholder="e.g. Termux"
              required
              bind:value={appName}
            />
          </div>

          <div class="mb-4">
            <label for="quick-app-url" class="label-text mb-1.5">ソースURL (GitHub / スクラップ対象) <span class="text-error-500">*</span></label>
            <input
              type="text"
              id="quick-app-url"
              class="input"
              placeholder="e.g. https://github.com/termux/termux-app"
              required
              disabled={urlDisabled}
              bind:value={appUrl}
            />
          </div>

          <div class="flex flex-wrap gap-4">
            <div class="min-w-[180px] flex-1">
              <label for="quick-app-source" class="label-text mb-1.5">ソース元タイプ</label>
              <Combobox
                placeholder="ソース元タイプ"
                openOnClick
                collection={sourceCollection}
                value={[appSource]}
                onValueChange={(details) => onSourceChange(details.value[0] ?? 'GitHub')}
              >
                <Combobox.Control>
                  <Combobox.Input id="quick-app-source" readonly />
                  <Combobox.Trigger data-testid="quick-app-source-trigger" />
                </Combobox.Control>
                <Combobox.Positioner>
                  <Combobox.Content class="z-[100]">
                    {#each sourceOptions as item (item.value)}
                      <Combobox.Item {item} data-testid={`quick-app-source-option-${item.value}`}>
                        <Combobox.ItemText>{item.label}</Combobox.ItemText>
                        <Combobox.ItemIndicator />
                      </Combobox.Item>
                    {/each}
                  </Combobox.Content>
                </Combobox.Positioner>
              </Combobox>
            </div>
            <div class="min-w-[180px] flex-1">
              <span class="label-text mb-1.5">カテゴリの選択</span>
              <div
                id="quick-categories-checkboxes"
                class="my-2 flex max-h-[120px] flex-col gap-1.5 overflow-y-auto rounded-container border border-surface-200-800 bg-surface-950/20 p-2"
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
                id="quick-app-categories"
                class="input field-sm"
                placeholder="新規追加（カンマ区切り）"
                bind:value={customCategories}
              />
            </div>
          </div>

          <div class="mt-6 flex gap-3">
            <button type="submit" class="btn preset-filled-primary-500" id="quick-save-btn">
              保存する
            </button>
            <button
              type="button"
              id="quick-detail-btn"
              class="btn preset-tonal {editMode ? '' : 'hidden'}"
              onclick={onDetail}
            >
              詳細設定へ ⚙️
            </button>
            <button
              type="button"
              class="btn preset-tonal"
              id="quick-cancel-btn"
              onclick={close}
            >
              キャンセル
            </button>
          </div>
        </form>
      </Dialog.Content>
    </Dialog.Positioner>
  </Portal>
</Dialog>
