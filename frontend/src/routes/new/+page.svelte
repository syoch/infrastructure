<script lang="ts">
  import { page } from '$app/state';
  import Dashboard from '../../views/Dashboard.svelte';

  const type = $derived(page.url.searchParams.get('type') ?? '');
  const params = $derived<Record<string, string>>({ type });
</script>

<div id="dashboard-view"><Dashboard routeName="new" {params}  /></div>
