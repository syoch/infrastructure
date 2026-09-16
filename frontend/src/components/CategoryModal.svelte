<script lang="ts">
  import { store, loadAllData } from '../lib/store.svelte.ts';
  import { navigate } from '../lib/router.svelte.ts';
  import { saveSettings, saveApp, type SaveAppPayload } from '../api/api.js';
  import { colorIntToHex, parseHexToColorInt, getCategoryModalColorPreview } from '../lib/ui.js';

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
      alert('既に存在するカテゴリ名です。');
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

      navigate('#list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      alert('カテゴリ設定または所属アプリの保存に失敗しました。');
    }
  }

  async function onDelete(): Promise<void> {
    if (!categoryName) return;
    if (
      !confirm(
        `カテゴリ "${categoryName}" を削除してもよろしいですか？ (登録アプリ自体のカテゴリ割り当ては別途変更が必要です)`
      )
    )
      return;
    try {
      const cats = { ...(store.settings.categories || {}) };
      delete cats[categoryName];
      await saveSettings({ categories: cats });
      navigate('#list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      alert('カテゴリの削除に失敗しました。');
    }
  }
</script>

<div id="category-modal" class="modal-backdrop" class:active={active}>
  <div class="modal-content" style="max-width:500px;">
    <button class="modal-close-btn" id="category-modal-close" type="button" aria-label="閉じる" onclick={() => navigate('#list')}>
      <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </button>

    <h2 class="card-title" id="category-modal-title">
      {isEdit ? `カテゴリ "${categoryName}" を編集` : 'カテゴリを作成'}
    </h2>
    <p class="card-subtitle">カテゴリ名とARGBカラーコードを設定します。10進数です。</p>

    <form id="category-modal-form" onsubmit={onSubmit}>
      <div class="form-group">
        <label for="cat-modal-name">カテゴリ名</label>
        <input type="text" id="cat-modal-name" required placeholder="e.g. customize" bind:value={name} />
      </div>

      <div class="form-group">
        <label for="cat-modal-color">カラーコード (Hex ARGB / RGB)</label>
        <div style="display:flex;gap:12px;align-items:center;">
          <input type="text" id="cat-modal-color" required placeholder="e.g. #88ffcc88 or #ffcc88" style="flex:1;" value={color} oninput={onColorInput} />
          <div
            id="cat-modal-color-preview"
            style="width:38px;height:38px;border-radius:8px;border:1px solid var(--border-color);transition:background-color 0.3s ease;"
            style:background-color={preview}
          ></div>
        </div>
      </div>

      <div class="form-group" style="margin-top:20px;">
        <span class="form-label" style="font-weight:600;margin-bottom:12px;display:block;">このカテゴリに所属させるアプリを選択</span>
        <div id="category-apps-list" class="categories-list" style="max-height:220px;background:rgba(0,0,0,0.15);padding:8px 12px;border-radius:var(--radius-sm);border:1px solid var(--border-color);overflow-y:auto;display:flex;flex-direction:column;gap:8px;">
          {#if !isEdit}
            <div style="color:var(--color-text-muted);font-size:0.8rem;padding:12px 0;">新しいカテゴリです。保存後、アプリに割り当ててください。</div>
          {:else if apps.length === 0}
            <div style="color:var(--color-text-muted);font-size:0.8rem;padding:12px 0;">登録されているアプリがありません。</div>
          {:else}
            {#each apps as app (app.id)}
              <label class="modal-app-item" style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:6px 8px;border-radius:4px;transition:background-color 0.2s;">
                <input type="checkbox" name="cat-app-checkbox" data-app-id={app.id} bind:checked={appChecked[app.id]} style="cursor:pointer;" />
                <div style="display:flex;flex-direction:column;cursor:pointer;flex:1;">
                  <span class="app-name-display" style="font-weight:500;font-size:0.85rem;">{app.name}</span>
                  <span class="app-pkg-display" style="font-size:0.7rem;color:var(--color-text-muted);">{app.id}</span>
                </div>
              </label>
            {/each}
          {/if}
        </div>
      </div>

      <div class="form-actions" style="margin-top:24px;">
        <button type="submit" class="btn btn-primary" style="flex:2;">保存する</button>
        <button
          type="button"
          id="cat-modal-delete"
          class="btn btn-secondary"
          style="color:#ff5252;border-color:rgba(255,82,82,0.2);flex:1;{isEdit ? 'display:inline-flex;' : 'display:none;'}"
          onclick={onDelete}
        >削除</button>
      </div>
    </form>
  </div>
</div>
