<script lang="ts">
  import { page } from '$app/state';
  import Dashboard from '../../views/Dashboard.svelte';
  import AppEdit from '../../views/AppEdit.svelte';

  const type = $derived(page.url.searchParams.get('type') ?? '');
  const id = $derived(page.url.searchParams.get('id') ?? '');
  const params = $derived<Record<string, string>>({ type, id });
  const isApp = $derived(type === 'app');
</script>

{#if isApp}
  <div id="app-edit-view" class="view-section active"><AppEdit {id} /></div>
{:else}
  <div id="dashboard-view" class="view-section active"><Dashboard routeName="edit" {params} /></div>
{/if}
