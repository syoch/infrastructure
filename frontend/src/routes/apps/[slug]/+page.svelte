<script lang="ts">
  import { page } from '$app/state';
  import AppPortal from '../../../views/AppPortal.svelte';

  const slug = $derived(page.params.slug ?? '');
</script>

<div id="apps-view" class="view-section active"><AppPortal {slug}  /></div>
