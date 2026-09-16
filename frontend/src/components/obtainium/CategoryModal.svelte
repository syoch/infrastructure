<script lang="ts">
  import { store, loadAllData } from '../../lib/store.svelte.ts';
  import { goto as navigate } from '$app/navigation';
  import { Dialog, Portal } from '@skeletonlabs/skeleton-svelte';
  import { saveSettings, saveApp, type SaveAppPayload } from '../../api/api.js';
  import { colorIntToHex, parseHexToColorInt, getCategoryModalColorPreview } from '../../lib/ui.js';
  import { confirmDialog } from '../../lib/dialogs.svelte.ts';
  import { showCustomToast } from '../../lib/toast.ts';

  let {
    active = false,
    categoryName = null,
  }: { active?: boolean; categoryName?: string | null } = $props();

  let isEdit = $state(false);
  let name = $state('');
  let color = $state('#ff7c4dff');
  let preview = $state('#7c4dff');
  let appChecked = $state<Record<string, boolean>>({});

  let lastKey: string | null = null;

  const apps = $derived(store.dashboardApps);

  $effect(() => {
    const key = active ? (categoryName ?? '__new__') : null;
    if (key === null) {
      lastKey = null;
      return;
    }
    if (key === lastKey) return;
    lastKey = key;
    openModal();
  });

  function close(): void {
    navigate('/list');
  }

  function openModal(): void {
    const edit = !!categoryName;
    isEdit = edit;
    const cats = store.settings.categories || {};
    if (!edit) {
      name = '';
      color = '#ff7c4dff';
      preview = '#7c4dff';
      appChecked = {};
      return;
    }
    name = categoryName as string;
    const code = cats[name] ?? 0;
    color = colorIntToHex(code);
    preview = getCategoryModalColorPreview(code);
    const next: Record<string, boolean> = {};
    store.dashboardApps.forEach((app) => {
      if ((app.categories || []).includes(name)) next[app.id] = true;
    });
    appChecked = next;
  }

  function onColorInput(e: Event): void {
    color = (e.currentTarget as HTMLInputElement).value;
    const val = parseHexToColorInt(color);
    preview = isNaN(val) ? 'transparent' : getCategoryModalColorPreview(val);
  }

  async function onSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    const trimmed = name.trim();
    const colorInt = parseHexToColorInt(color);
    if (!trimmed || isNaN(colorInt)) return;

    const cats: Record<string, number> = { ...(store.settings.categories || {}) };
    const isNameChanged = isEdit && !!categoryName && categoryName !== trimmed;
    if (isNameChanged && cats[trimmed] !== undefined) {
      showCustomToast('既に存在するカテゴリ名です。', 'error');
      return;
    }
    if (isNameChanged && categoryName) delete cats[categoryName];
    cats[trimmed] = colorInt;

    try {
      await saveSettings({ categories: cats });

      if (isEdit) {
        const promises: Promise<unknown>[] = [];
        store.dashboardApps.forEach((app) => {
          const shouldHave = !!appChecked[app.id];
          let newCats = [...(app.categories || [])];
          let changed = false;
          if (isNameChanged && categoryName && newCats.includes(categoryName)) {
            newCats = newCats.filter((c) => c !== categoryName);
            changed = true;
          }
          const has = newCats.includes(trimmed);
          if (shouldHave && !has) {
            newCats.push(trimmed);
            changed = true;
          } else if (!shouldHave && has) {
            newCats = newCats.filter((c) => c !== trimmed);
            changed = true;
          }
          if (changed) {
            promises.push(
              saveApp({
                ...app,
                categories: newCats,
                additionalSettings: app.additionalSettings,
              } as SaveAppPayload)
            );
          }
        });
        if (promises.length > 0) await Promise.all(promises);
      }

      navigate('/list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast('カテゴリ設定または所属アプリの保存に失敗しました。', 'error');
    }
  }

  async function onDelete(): Promise<void> {
    if (!categoryName) return;
    const confirmed = await confirmDialog({
      title: 'カテゴリを削除',
      message: `カテゴリ "${categoryName}" を削除してもよろしいですか？ (登録アプリ自体のカテゴリ割り当ては別途変更が必要です)`,
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      const cats = { ...(store.settings.categories || {}) };
      delete cats[categoryName];
      await saveSettings({ categories: cats });
      navigate('/list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast('カテゴリの削除に失敗しました。', 'error');
    }
  }
</script>

<Dialog
  open={active}
  aria-label="カテゴリ編集"
  onOpenChange={(details) => {
    if (!details.open) close();
  }}
>
  <Portal>
    <Dialog.Backdrop class="fixed inset-0 z-[80] bg-surface-950/60" />
    <Dialog.Positioner class="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <Dialog.Content
        id="category-modal"
        data-testid="category-modal"
        class="card bg-surface-100-900 relative max-h-[90vh] w-full max-w-lg overflow-y-auto p-6 shadow-xl"
      >
        <button
          class="preset-tonal absolute top-3 right-3 h-4 w-4"
          id="category-modal-close"
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
            <h2 {...attributes} id="category-modal-title" class="h4">
              {isEdit ? `カテゴリ "${categoryName}" を編集` : 'カテゴリを作成'}
            </h2>
          {/snippet}
        </Dialog.Title>
        <p class="mt-1 text-sm text-surface-600-400">カテゴリ名とARGBカラーコードを設定します。10進数です。</p>

        <form id="category-modal-form" onsubmit={onSubmit} class="mt-4">
          <div class="mb-4">
            <label for="cat-modal-name" class="label-text mb-1.5">カテゴリ名</label>
            <input
              type="text"
              id="cat-modal-name"
              class="input"
              required
              placeholder="e.g. customize"
              bind:value={name}
            />
          </div>

          <div class="mb-4">
            <label for="cat-modal-color" class="label-text mb-1.5">カラーコード (Hex ARGB / RGB)</label>
            <div class="flex items-center gap-3">
              <input
                type="text"
                id="cat-modal-color"
                class="input flex-1"
                required
                placeholder="e.g. #88ffcc88 or #ffcc88"
                value={color}
                oninput={onColorInput}
              />
              <div
                id="cat-modal-color-preview"
                class="size-[38px] rounded border border-surface-200-800 transition-colors"
                style:background-color={preview}
              ></div>
            </div>
          </div>

          <div class="mt-5">
            <span class="label-text mb-3 font-semibold">このカテゴリに所属させるアプリを選択</span>
            <div
              id="category-apps-list"
              class="flex max-h-[220px] flex-col gap-2 overflow-y-auto rounded-container border border-surface-200-800 bg-surface-950/20 p-2"
            >
              {#if !isEdit}
                <div class="py-3 text-xs text-surface-600-400">
                  新しいカテゴリです。保存後、アプリに割り当ててください。
                </div>
              {:else if apps.length === 0}
                <div class="py-3 text-xs text-surface-600-400">登録されているアプリがありません。</div>
              {:else}
                {#each apps as app (app.id)}
                  <label
                    class="flex cursor-pointer items-center gap-2.5 rounded p-1.5 transition-colors hover:preset-tonal"
                  >
                    <input
                      type="checkbox"
                      name="cat-app-checkbox"
                      class="checkbox"
                      data-app-id={app.id}
                      bind:checked={appChecked[app.id]}
                    />
                    <div class="flex flex-1 cursor-pointer flex-col">
                      <span class="text-sm font-medium">{app.name}</span>
                      <span class="text-[0.7rem] text-surface-600-400">{app.id}</span>
                    </div>
                  </label>
                {/each}
              {/if}
            </div>
          </div>

          <div class="mt-6 flex gap-3">
            <button type="submit" class="btn preset-filled-primary-500 flex-[2]">保存する</button>
            <button
              type="button"
              id="cat-modal-delete"
              class="btn preset-tonal-error flex-1 {isEdit ? '' : 'hidden'}"
              onclick={onDelete}
            >
              削除
            </button>
          </div>
        </form>
      </Dialog.Content>
    </Dialog.Positioner>
  </Portal>
</Dialog>
