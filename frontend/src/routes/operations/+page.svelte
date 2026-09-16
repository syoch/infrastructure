<script lang="ts">
  import { page } from '$app/state';
  import Operations from '../../views/Operations.svelte';

  const params = $derived<Record<string, string>>(
    Object.fromEntries(page.url.searchParams.entries())
  );
</script>

<div id="operations-view" class="view-section active"><Operations {params}  /></div>
