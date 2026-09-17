<script lang="ts">
  import { untrack } from 'svelte';
  import { fetchTokens, issueToken, deleteToken, type BootstrapToken } from '../../../api/control_api.js';
  import { showCustomToast } from '../../../lib/toast.ts';
  import { confirmDialog, promptDialog } from '../../../lib/dialogs.svelte.ts';
  import { msg, formatDate, tokenStatus } from '../../../components/control_plane/format.js';

  let tokens = $state<BootstrapToken[]>([]);
  let error = $state('');

  $effect(() => {
    untrack(() => {
      void refresh();
    });
  });

  async function refresh(): Promise<void> {
    try {
      tokens = await fetchTokens();
      error = '';
    } catch (e) {
      error = msg(e);
    }
  }

  async function onIssue(): Promise<void> {
    const deviceId = await promptDialog({
      title: 'Bootstrap トークン発行',
      label: 'Target Device ID (e.g. tablet-01):',
    });
    if (!deviceId) return;
    const displayName = await promptDialog({
      title: 'Bootstrap トークン発行',
      label: 'Display Name (e.g. My Android Tablet):',
    });
    if (!displayName) return;
    const ttlRaw = await promptDialog({
      title: 'Bootstrap トークン発行',
      label: 'TTL in minutes (default 15):',
      defaultValue: '15',
    });
    const ttl = ttlRaw ? parseInt(ttlRaw, 10) : 15;
    try {
      const res = await issueToken({ device_id: deviceId, display_name: displayName, ttl_minutes: ttl });
      showCustomToast(
        `Token issued successfully!\n\nID: ${res.id}\n\nNOTE: This token will not be shown again. Copy it now.`,
        'success',
        10000
      );
      await refresh();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  async function onRevoke(tokenId: string): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'トークンを失効',
      message: `Bootstrap Token ${tokenId.substring(0, 8)}... を失効させますか?`,
      confirmText: '失効',
    });
    if (!confirmed) return;
    try {
      await deleteToken(tokenId);
      await refresh();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }
</script>

<section class="card bg-surface-100-900 mt-10 mb-6 space-y-4 p-6">
  <header class="mb-4 flex flex-wrap items-center justify-between gap-2">
    <h2 class="h2">Bootstrap Tokens</h2>
    <button type="button" class="btn preset-filled-primary-500" id="issue-token-btn" onclick={onIssue}>
      Issue Token
    </button>
  </header>
  <div id="tokens-list" class="card bg-surface-100-900 overflow-x-auto">
    {#if error}
      <p class="preset-tonal-error rounded-base p-4 text-sm">Error: {error}</p>
    {:else if tokens.length === 0}
      <p class="p-4 text-surface-600-400">No bootstrap tokens issued.</p>
    {:else}
      <table class="table">
        <thead>
          <tr><th>Token</th><th>Target Device</th><th>Expires</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {#each tokens as bootstrapToken (bootstrapToken.id)}
            {@const status = tokenStatus(bootstrapToken)}
            <tr>
              <td><code>{bootstrapToken.id.substring(0, 8)}...</code></td>
              <td>
                <div class="font-medium">{bootstrapToken.device_id}</div>
                <div class="text-xs text-surface-600-400">{bootstrapToken.display_name}</div>
              </td>
              <td>{formatDate(bootstrapToken.expires_at)}</td>
              <td><span class={status.cls}>{status.label}</span></td>
              <td>
                <button
                  type="button"
                  class="btn preset-tonal-error"
                  onclick={() => onRevoke(bootstrapToken.id)}
                >
                  Revoke
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</section>
