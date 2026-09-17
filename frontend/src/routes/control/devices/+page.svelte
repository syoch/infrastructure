<script lang="ts">
  import { untrack } from 'svelte';
  import { ensureMe } from '../../../lib/auth.svelte.ts';
  import { getToken, type Device } from '../../../api/control_api.js';
  import BootstrapForm from '../../../components/control_plane/BootstrapForm.svelte';
  import DevicesPanel from './DevicesPanel.svelte';
  import TokensPanel from './TokensPanel.svelte';

  type Phase = 'loading' | 'bootstrap' | 'ready';

  let token = $state<string | null>(getToken());
  let me = $state<Device | null>(null);
  let phase = $state<Phase>('loading');

  const isAdmin = $derived(me?.is_first_webui_device === true);

  $effect(() => {
    const currentToken = token;
    untrack(() => {
      void load(currentToken);
    });
  });

  async function load(currentToken: string | null): Promise<void> {
    if (!currentToken) {
      me = null;
      phase = 'bootstrap';
      return;
    }
    phase = 'loading';
    const fetched = await ensureMe(true);
    if (!fetched) {
      me = null;
      phase = 'bootstrap';
      return;
    }
    me = fetched;
    phase = 'ready';
  }

  function onRegistered(): void {
    token = getToken();
  }
</script>

<div id="control-view">
  {#if phase === 'loading'}
    <section class="card bg-surface-100-900 p-6" aria-busy="true">
      <span class="sr-only">Loading…</span>
      <div class="placeholder mb-4 h-6 w-40"></div>
      <div class="placeholder h-4 w-full"></div>
    </section>
  {:else if phase === 'bootstrap'}
    <BootstrapForm onRegistered={onRegistered} />
  {:else if phase === 'ready' && me}
    <DevicesPanel {me} />
    {#if isAdmin}
      <TokensPanel />
    {/if}
  {/if}
</div>
