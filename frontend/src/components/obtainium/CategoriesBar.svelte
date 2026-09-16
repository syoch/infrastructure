<script lang="ts">
  import { goto as navigate } from '$app/navigation';
  import { store } from '../../lib/store.svelte.ts';
  import { getCategoryColorStyle } from '../../lib/ui.js';

  const categories = $derived(store.settings.categories || {});

  function openCategory(name: string): void {
    navigate(`/edit?type=category&id=${encodeURIComponent(name)}`);
  }
</script>

<section class="categories-bar-section mb-8">
  <div class="card bg-surface-100-900 border border-surface-200-800 p-5 backdrop-blur">
    <h3 class="label-text mb-3 uppercase tracking-wide text-surface-700-300">カテゴリ一覧と編集</h3>
    <div id="dashboard-categories-bar" class="flex flex-wrap items-center gap-2">
      {#each Object.entries(categories) as [catName, colorCode] (catName)}
        <button
          type="button"
          class="chip cursor-pointer"
          data-testid="category-tag"
          data-name={catName}
          style={getCategoryColorStyle(colorCode)}
          onclick={() => openCategory(catName)}
        >{catName}</button>
      {/each}
      <button
        id="add-category-btn"
        class="chip cursor-pointer border border-dashed border-surface-300-700"
        onclick={() => navigate('/new?type=category')}
      >
        ➕ 新規カテゴリ追加
      </button>
    </div>
  </div>
</section>
