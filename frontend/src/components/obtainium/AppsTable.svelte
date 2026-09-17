<script lang="ts">
  import { goto as navigate } from '$app/navigation';
  import { store, loadAllData } from '../../lib/store.svelte.ts';
  import { deleteApp, type App } from '../../api/api.js';
  import { getCategoryColorStyle, validateUrlSourceMatch } from '../../lib/ui.js';
  import { showCustomToast } from '../../lib/toast.ts';
  import { confirmDialog } from '../../lib/dialogs.svelte.ts';
  import { compareAppsByCategory } from '../../lib/sort.ts';
  import SortHeader from './SortHeader.svelte';
  import Edit from '@lucide/svelte/icons/pencil';
  import Trash from '@lucide/svelte/icons/trash';

  type SortDirection = 'asc' | 'desc' | null;

  let sortDirection = $state<SortDirection>(null);

  const apps = $derived(store.dashboardApps);
  const categories = $derived(store.settings.categories || {});

  const sortedApps = $derived.by(() => {
    if (!sortDirection) return [...apps];
    return [...apps].sort((a, b) => compareAppsByCategory(a, b, sortDirection as 'asc' | 'desc'));
  });

  function onSortClick(): void {
    if (sortDirection === null) sortDirection = 'asc';
    else if (sortDirection === 'asc') sortDirection = 'desc';
    else sortDirection = null;
  }

  function openEdit(id: string): void {
    navigate(`/edit?type=app&id=${encodeURIComponent(id)}`);
  }

  function openCategory(name: string): void {
    navigate(`/edit?type=category&id=${encodeURIComponent(name)}`);
  }

  function sourceLabel(app: App): string {
    const { valid, warning } = validateUrlSourceMatch(app.url, app.overrideSource);
    return !valid && warning ? `⚠️ ${app.overrideSource}` : app.overrideSource || 'Auto';
  }

  function sourceWarning(app: App): string | null {
    const { valid, warning } = validateUrlSourceMatch(app.url, app.overrideSource);
    return !valid ? warning : null;
  }

  async function onDeleteApp(id: string): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'アプリを削除',
      message: `アプリ '${id}' を削除してもよろしいですか？`,
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteApp(id);
      navigate('/list');
      await loadAllData();
    } catch (err) {
      console.error(err);
      showCustomToast('アプリの削除に失敗しました。', 'error');
    }
  }
</script>

<section class="dashboard-list-section mb-8" data-testid="dashboard-list-section">
  <h2 class="h3 mb-4">登録アプリ一覧</h2>
  <div class="table-wrap card bg-surface-100-900 border border-surface-200-800">
    <table class="table">
      <thead>
        <tr>
          <th>アプリ名 / ID</th>
          <th>
            <SortHeader
              id="dashboard-sort-category"
              iconId="dashboard-sort-icon"
              direction={sortDirection}
              onclick={onSortClick}
            />
          </th>
          <th>ソース</th>
          <th class="pr-8 text-right">操作</th>
        </tr>
      </thead>
      <tbody id="dashboard-apps-list">
        {#if sortedApps.length === 0}
          <tr data-testid="empty-row">
            <td colspan="4" class="p-8 text-center text-surface-600-400">
              登録されているアプリがありません。新規アプリ登録から追加してください。
            </td>
          </tr>
        {:else}
          {#each sortedApps as app (app.id)}
            <tr data-testid="app-row">
              <td>
                <div class="flex flex-col gap-1">
                  <span class="font-bold" data-testid="app-name-text">{app.name}</span>
                  <span class="font-mono text-xs text-surface-600-400">{app.id}</span>
                </div>
              </td>
              <td>
                <div class="flex flex-wrap gap-1.5" data-testid="category-tags">
                  {#each app.categories as cat (cat)}
                    <button
                      type="button"
                      class="chip cursor-pointer"
                      data-testid="category-tag"
                      data-cat={cat}
                      style={getCategoryColorStyle(categories[cat])}
                      onclick={() => openCategory(cat)}>{cat}</button
                    >
                  {/each}
                </div>
              </td>
              <td>
                <span>{sourceLabel(app)}</span>
                {#if sourceWarning(app)}
                  <div class="text-xs text-warning-500" title={sourceWarning(app)}>
                    {sourceWarning(app)}
                  </div>
                {/if}
              </td>
              <td class="text-right">
                <div class="flex items-center justify-end gap-2">
                  <button
                    class="btn preset-tonal btn-sm quick-edit-btn"
                    onclick={() => openEdit(app.id)}
                  >
                    <Edit class="w-4 h-4" />
                  </button>
                  <button
                    class="btn preset-tonal-error btn-sm delete-app-btn"
                    onclick={() => onDeleteApp(app.id)}
                  >
                    <Trash class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</section>
