<script lang="ts">
  import { onMount } from 'svelte';
  import { runSchemaHarness, type HarnessResult } from '$lib/schema_harness';

  let results = $state<HarnessResult[]>([]);

  onMount(() => {
    results = runSchemaHarness();
    (window as unknown as Record<string, unknown>).__testResults = results;
    (window as unknown as Record<string, unknown>).__testDone = true;
  });
</script>

<h1>Schema Renderer Test Harness</h1>
<div id="root"></div>
<pre id="results">{JSON.stringify(results, null, 2)}</pre>
