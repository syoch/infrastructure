<script lang="ts">
  import { untrack } from 'svelte';
  import { auth, ensureMe } from '../lib/auth.svelte.ts';
  import { goto as navigate } from '$app/navigation';
  import { Switch } from '@skeletonlabs/skeleton-svelte';
  import {
    getToken,
    setToken,
    registerDevice,
    fetchDevices,
    setAdmin,
    deleteDevice,
    fetchTokens,
    issueToken,
    deleteToken,
    fetchAcl,
    createAcl,
    deleteAcl,
    type Device,
    type BootstrapToken,
    type ACL,
  } from '../api/control_api.js';
  import { showCustomToast } from '../lib/toast.ts';
  import { confirmDialog, promptDialog } from '../lib/dialogs.svelte.ts';

  let { sub = '' }: { sub?: string } = $props();

  type Phase = 'loading' | 'bootstrap' | 'devices' | 'acl' | 'error';

  let token = $state<string | null>(getToken());
  let me = $state<Device | null>(null);
  let phase = $state<Phase>('loading');
  let errorMessage = $state('');

  let devices = $state<Device[]>([]);
  let tokens = $state<BootstrapToken[]>([]);
  let acls = $state<ACL[]>([]);

  let devicesError = $state('');
  let tokensError = $state('');
  let aclError = $state('');

  let bootDeviceId = $state('webui');
  let bootDisplayName = $state('WebUI');
  let bootToken = $state('');
  let bootError = $state('');
  let bootBusy = $state(false);

  let aclSource = $state('');
  let aclTarget = $state('');
  let aclOp = $state('');
  let aclExtra = $state('');

  const isAdmin = $derived(me?.is_first_webui_device === true);

  function msg(e: unknown): string {
    return e instanceof Error ? e.message : String(e);
  }

  $effect(() => {
    const currentSub = sub;
    const currentToken = token;
    // ensureMe() reads/writes the shared auth $state; keep that out of this
    // effect's dependency graph so it does not re-trigger itself.
    untrack(() => {
      void load(currentSub, currentToken);
    });
  });

  async function load(currentSub: string, currentToken: string | null): Promise<void> {
    if (!currentToken) {
      me = null;
      phase = 'bootstrap';
      return;
    }
    phase = 'loading';
    // Always fetch fresh: the token can be set without a full page reload
    // (e.g. direct hash navigation after localStorage changes), in which case
    // the cached "no token" state would otherwise stick.
    const fetched = await ensureMe(true);
    if (!fetched) {
      me = null;
      auth.me = null;
      errorMessage = '';
      phase = 'bootstrap';
      return;
    }
    me = fetched;
    const target = currentSub || 'devices';
    if (target === 'acl') {
      phase = 'acl';
      await refreshAcls();
    } else {
      phase = 'devices';
      await refreshDevices();
    }
  }

  async function refreshDevices(): Promise<void> {
    try {
      devices = await fetchDevices();
      devicesError = '';
    } catch (e) {
      devicesError = msg(e);
    }
    if (isAdmin) await refreshTokens();
  }

  async function refreshTokens(): Promise<void> {
    try {
      tokens = await fetchTokens();
      tokensError = '';
    } catch (e) {
      tokensError = msg(e);
    }
  }

  async function refreshAcls(): Promise<void> {
    if (!isAdmin) return;
    try {
      acls = await fetchAcl();
      aclError = '';
    } catch (e) {
      aclError = msg(e);
    }
  }

  async function onBootstrapSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    bootError = '';
    bootBusy = true;
    try {
      const result = await registerDevice({
        device_id: bootDeviceId,
        display_name: bootDisplayName,
        bootstrap_token: bootToken,
      });
      setToken(result.bearer_token, result.id);
      await ensureMe(true);
      token = getToken();
      navigate('/control/devices');
    } catch (err) {
      bootError = msg(err);
    } finally {
      bootBusy = false;
    }
  }

  async function onAdminToggle(device: Device, value: boolean): Promise<void> {
    const prompt = value
      ? `${device.id} を admin に昇格しますか?`
      : `${device.id} から admin を剥奪しますか?`;
    const confirmed = await confirmDialog({ title: 'Admin 権限の変更', message: prompt });
    if (!confirmed) return;
    try {
      await setAdmin(device.id, value);
      await refreshDevices();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  async function onDeleteDevice(device: Device): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'デバイスを削除',
      message: `Device ${device.id} を削除しますか?`,
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteDevice(device.id);
      await refreshDevices();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  async function onIssueToken(): Promise<void> {
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
      await refreshTokens();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  async function onRevokeToken(tokenId: string): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'トークンを失効',
      message: `Bootstrap Token ${tokenId.substring(0, 8)}... を失効させますか?`,
      confirmText: '失効',
    });
    if (!confirmed) return;
    try {
      await deleteToken(tokenId);
      await refreshTokens();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  async function onAclSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    try {
      await createAcl({
        source_device: aclSource,
        target_device: aclTarget,
        operation: aclOp,
        extra: aclExtra || '',
      });
      aclSource = '';
      aclTarget = '';
      aclOp = '';
      aclExtra = '';
      await refreshAcls();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  async function onAclDelete(aclId: string): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'ACL を削除',
      message: 'この ACL を削除しますか?',
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteAcl(aclId);
      await refreshAcls();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  function wsBadge(state: string | undefined): string {
    if (state === 'online') return 'badge preset-filled-success-500';
    if (state === 'offline') return 'badge preset-tonal-surface';
    return 'badge preset-filled-warning-500';
  }

  function formatDate(value: string | null | undefined): string {
    if (!value) return '—';
    return value.toString().replace('T', ' ').substring(0, 19);
  }

  function tokenStatus(t: BootstrapToken): { label: string; cls: string } {
    if (t.consumed_at) return { label: 'Consumed', cls: 'badge preset-tonal-surface' };
    if (new Date(t.expires_at) < new Date()) return { label: 'Expired', cls: 'badge preset-filled-error-500' };
    return { label: 'Pending', cls: 'badge preset-filled-success-500' };
  }
</script>

{#if phase === 'bootstrap'}
  <section class="card bg-surface-100-900 mx-auto mt-16 max-w-[30rem] p-8">
    <h2 class="h2 mb-3">WebUI セットアップ</h2>
    <p class="mb-3 text-sm text-surface-600-400">
      この WebUI を使うには、まずサーバー側で bootstrap トークンを発行してください:
    </p>
    <pre class="pre mt-4 mb-6">portal-manage control issue-bootstrap-token \
  --device-id webui \
  --display-name "WebUI"</pre>
    <form id="bootstrap-form" class="mt-6 flex flex-col gap-3" onsubmit={onBootstrapSubmit}>
      <label class="label" for="bootstrap-device-id">
        <span class="label-text">Device ID</span>
        <input id="bootstrap-device-id" name="device_id" class="input" bind:value={bootDeviceId} required />
      </label>
      <label class="label" for="bootstrap-display-name">
        <span class="label-text">Display name</span>
        <input id="bootstrap-display-name" name="display_name" class="input" bind:value={bootDisplayName} required />
      </label>
      <label class="label" for="bootstrap-token">
        <span class="label-text">Bootstrap token</span>
        <input id="bootstrap-token" name="bootstrap_token" class="input font-mono" bind:value={bootToken} required />
      </label>
      <button type="submit" class="btn preset-filled-primary-500 w-full" disabled={bootBusy}>セットアップ</button>
      <div id="bootstrap-error" class="text-sm text-error-500">{bootError}</div>
    </form>
  </section>
{:else if phase === 'error'}
  <div class="p-10 text-center text-error-500">Error: {errorMessage}</div>
{:else if phase === 'acl'}
  <section class="card bg-surface-100-900 mb-6 space-y-4 p-6">
    <header class="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h2 class="h2">ACL</h2>
    </header>
    {#if !isAdmin}
      <div data-testid="control-guard" class="card bg-surface-100-900 space-y-4 p-10 text-center text-surface-600-400">
        <p>
          この画面は admin 専用です。現在のデバイス <code>{me?.id || '(unknown)'}</code> には admin 権限がありません。
        </p>
        <a href="/control/devices" class="btn preset-filled-primary-500">Devices に戻る</a>
      </div>
    {:else}
      <form id="acl-form" class="grid gap-2 sm:grid-cols-2 lg:grid-cols-5" onsubmit={onAclSubmit}>
        <input
          name="source_device"
          class="input"
          placeholder="device:source-*"
          pattern="^device:.+"
          bind:value={aclSource}
          required
        />
        <input
          name="target_device"
          class="input"
          placeholder="device:target-*"
          pattern="^device:.+"
          bind:value={aclTarget}
          required
        />
        <input name="operation" class="input" placeholder="op regex (e.g. .*)" bind:value={aclOp} required />
        <input name="extra" class="input" placeholder="extra (optional)" bind:value={aclExtra} />
        <button type="submit" class="btn preset-filled-primary-500">追加</button>
      </form>
      {#if aclError}
        <p class="text-error-500">Error: {aclError}</p>
      {/if}
      <div class="table-wrap card bg-surface-100-900 overflow-x-auto">
        <table class="table">
          <thead>
            <tr><th>Source</th><th>Target</th><th>Op</th><th>Extra</th><th></th></tr>
          </thead>
          <tbody id="acl-tbody">
            {#each acls as acl (acl.id)}
              <tr>
                <td><code>{acl.source_device}</code></td>
                <td><code>{acl.target_device}</code></td>
                <td><code>{acl.operation}</code></td>
                <td><code>{acl.extra || ''}</code></td>
                <td>
                  <button
                    type="button"
                    class="btn preset-tonal-error"
                    onclick={() => onAclDelete(acl.id)}
                  >
                    削除
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
{:else if phase === 'devices'}
  <section class="card bg-surface-100-900 mb-6 space-y-4 p-6">
    <header class="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h2 class="h2">Devices</h2>
      <span class="font-mono text-sm text-surface-600-400">{me?.id || ''}{isAdmin ? ' (admin)' : ''}</span>
    </header>
    <div id="devices-list" class="card bg-surface-100-900 overflow-x-auto">
      {#if devicesError}
        <p class="p-4 text-error-500">Error: {devicesError}</p>
      {:else if devices.length === 0}
        <p class="p-4 text-surface-600-400">No devices registered.</p>
      {:else}
        <table class="table">
          <thead>
            <tr>
              <th>ID</th><th>Display</th><th>WS</th><th>Last seen</th>
              {#if isAdmin}<th>Admin</th><th></th>{/if}
            </tr>
          </thead>
          <tbody>
            {#each devices as device (device.id)}
              <tr>
                <td><code>{device.id}</code></td>
                <td>{device.display_name || ''}</td>
                <td>
                  <span class={wsBadge(device.ws_state)}>
                    {device.ws_state || 'never_connected'}
                  </span>
                </td>
                <td>{formatDate(device.last_seen)}</td>
                {#if isAdmin}
                  <td>
                    <Switch
                      label={`Admin ${device.id}`}
                      checked={device.is_first_webui_device}
                      onCheckedChange={(details) => onAdminToggle(device, details.checked)}
                    >
                      <Switch.Control><Switch.Thumb /></Switch.Control>
                    </Switch>
                  </td>
                  <td>
                    <button
                      type="button"
                      class="btn preset-tonal-error"
                      onclick={() => onDeleteDevice(device)}
                    >
                      Delete
                    </button>
                  </td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  </section>

  {#if isAdmin}
    <section class="card bg-surface-100-900 mt-10 mb-6 space-y-4 p-6">
      <header class="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 class="h2">Bootstrap Tokens</h2>
        <button type="button" class="btn preset-filled-primary-500" id="issue-token-btn" onclick={onIssueToken}>
          Issue Token
        </button>
      </header>
      <div id="tokens-list" class="card bg-surface-100-900 overflow-x-auto">
        {#if tokensError}
          <p class="p-4 text-error-500">Error: {tokensError}</p>
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
                      onclick={() => onRevokeToken(bootstrapToken.id)}
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
  {/if}
{/if}
