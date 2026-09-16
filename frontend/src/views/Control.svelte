<script lang="ts">
  import { untrack } from 'svelte';
  import { auth, ensureMe } from '../lib/auth.svelte.ts';
  import { navigate } from '../lib/router.svelte.ts';
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
  } from '../../js/control_api.js';

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
      navigate('#/control/devices');
    } catch (err) {
      bootError = msg(err);
    } finally {
      bootBusy = false;
    }
  }

  async function onAdminToggle(device: Device, e: Event): Promise<void> {
    const input = e.currentTarget as HTMLInputElement;
    const value = input.checked;
    const prompt = value
      ? `${device.id} を admin に昇格しますか?`
      : `${device.id} から admin を剥奪しますか?`;
    if (!confirm(prompt)) {
      input.checked = !value;
      return;
    }
    try {
      await setAdmin(device.id, value);
      await refreshDevices();
    } catch (err) {
      alert(msg(err));
      input.checked = !value;
    }
  }

  async function onDeleteDevice(device: Device): Promise<void> {
    if (!confirm(`Device ${device.id} を削除しますか?`)) return;
    try {
      await deleteDevice(device.id);
      await refreshDevices();
    } catch (err) {
      alert(msg(err));
    }
  }

  async function onIssueToken(): Promise<void> {
    const deviceId = prompt('Target Device ID (e.g. tablet-01):');
    if (!deviceId) return;
    const displayName = prompt('Display Name (e.g. My Android Tablet):');
    if (!displayName) return;
    const ttlRaw = prompt('TTL in minutes (default 15):', '15');
    const ttl = ttlRaw ? parseInt(ttlRaw, 10) : 15;
    try {
      const res = await issueToken({ device_id: deviceId, display_name: displayName, ttl_minutes: ttl });
      alert(`Token issued successfully!\n\nID: ${res.id}\n\nNOTE: This token will not be shown again. Copy it now.`);
      await refreshTokens();
    } catch (err) {
      alert(msg(err));
    }
  }

  async function onRevokeToken(tokenId: string): Promise<void> {
    if (!confirm(`Bootstrap Token ${tokenId.substring(0, 8)}... を失効させますか?`)) return;
    try {
      await deleteToken(tokenId);
      await refreshTokens();
    } catch (err) {
      alert(msg(err));
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
      alert(msg(err));
    }
  }

  async function onAclDelete(aclId: string): Promise<void> {
    if (!confirm('この ACL を削除しますか?')) return;
    try {
      await deleteAcl(aclId);
      await refreshAcls();
    } catch (err) {
      alert(msg(err));
    }
  }

  function wsColor(state: string | undefined): string {
    if (state === 'online') return '#20a020';
    if (state === 'offline') return '#888';
    return '#f0a020';
  }

  function formatDate(value: string | null | undefined): string {
    if (!value) return '—';
    return value.toString().replace('T', ' ').substring(0, 19);
  }

  function tokenStatus(t: BootstrapToken): { label: string; color: string } {
    if (t.consumed_at) return { label: 'Consumed', color: '#888' };
    if (new Date(t.expires_at) < new Date()) return { label: 'Expired', color: '#ff5252' };
    return { label: 'Pending', color: '#20a020' };
  }
</script>

{#if phase === 'bootstrap'}
  <section class="bootstrap-section">
    <h2>WebUI セットアップ</h2>
    <p class="bootstrap-hint">この WebUI を使うには、まずサーバー側で bootstrap トークンを発行してください:</p>
    <pre class="bootstrap-pre">portal-manage control issue-bootstrap-token \
  --device-id webui \
  --display-name "WebUI"</pre>
    <form id="bootstrap-form" class="bootstrap-form" onsubmit={onBootstrapSubmit}>
      <label for="bootstrap-device-id">Device ID</label>
      <input id="bootstrap-device-id" name="device_id" bind:value={bootDeviceId} required />
      <label for="bootstrap-display-name">Display name</label>
      <input id="bootstrap-display-name" name="display_name" bind:value={bootDisplayName} required />
      <label for="bootstrap-token">Bootstrap token</label>
      <input id="bootstrap-token" name="bootstrap_token" class="mono" bind:value={bootToken} required />
      <button type="submit" class="btn btn-primary" disabled={bootBusy}>セットアップ</button>
      <div id="bootstrap-error" class="bootstrap-error">{bootError}</div>
    </form>
  </section>
{:else if phase === 'error'}
  <div class="control-error">Error: {errorMessage}</div>
{:else if phase === 'acl'}
  <section class="control-section">
    <header class="control-section-header"><h2>ACL</h2></header>
    {#if !isAdmin}
      <div class="control-guard">
        <p>
          この画面は admin 専用です。現在のデバイス <code>{me?.id || '(unknown)'}</code> には admin 権限がありません。
        </p>
        <a href="#/control/devices" class="btn btn-primary">Devices に戻る</a>
      </div>
    {:else}
      <form id="acl-form" class="control-form" onsubmit={onAclSubmit}>
        <input
          name="source_device"
          placeholder="device:source-*"
          pattern="^device:.+"
          bind:value={aclSource}
          required
        />
        <input
          name="target_device"
          placeholder="device:target-*"
          pattern="^device:.+"
          bind:value={aclTarget}
          required
        />
        <input name="operation" placeholder="op regex (e.g. .*)" bind:value={aclOp} required />
        <input name="extra" placeholder="extra (optional)" bind:value={aclExtra} />
        <button type="submit" class="btn btn-primary">追加</button>
      </form>
      {#if aclError}
        <p style="color: #ff5252;">Error: {aclError}</p>
      {/if}
      <table class="control-table">
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
                  class="btn btn-secondary"
                  style="color: #ff5252;"
                  onclick={() => onAclDelete(acl.id)}
                >
                  削除
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
{:else if phase === 'devices'}
  <section class="control-section">
    <header class="control-section-header">
      <h2>Devices</h2>
      <span class="control-section-subtitle">{me?.id || ''}{isAdmin ? ' (admin)' : ''}</span>
    </header>
    <div id="devices-list">
      {#if devicesError}
        <p style="color: #ff5252;">Error: {devicesError}</p>
      {:else if devices.length === 0}
        <p style="color: #888;">No devices registered.</p>
      {:else}
        <table class="control-table">
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
                  <span style="color: {wsColor(device.ws_state)};">
                    {device.ws_state || 'never_connected'}
                  </span>
                </td>
                <td>{formatDate(device.last_seen)}</td>
                {#if isAdmin}
                  <td>
                    <input
                      type="checkbox"
                      checked={device.is_first_webui_device}
                      onchange={(e) => onAdminToggle(device, e)}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      class="btn btn-secondary"
                      style="color: #ff5252;"
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
    <section class="control-section" style="margin-top: 40px;">
      <header class="control-section-header">
        <h2>Bootstrap Tokens</h2>
        <button type="button" class="btn btn-primary" id="issue-token-btn" onclick={onIssueToken}>
          Issue Token
        </button>
      </header>
      <div id="tokens-list">
        {#if tokensError}
          <p style="color: #ff5252;">Error: {tokensError}</p>
        {:else if tokens.length === 0}
          <p style="color: #888;">No bootstrap tokens issued.</p>
        {:else}
          <table class="control-table">
            <thead>
              <tr><th>Token</th><th>Target Device</th><th>Expires</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {#each tokens as bootstrapToken (bootstrapToken.id)}
                {@const status = tokenStatus(bootstrapToken)}
                <tr>
                  <td><code>{bootstrapToken.id.substring(0, 8)}...</code></td>
                  <td>
                    <div style="font-weight: 500;">{bootstrapToken.device_id}</div>
                    <div style="font-size: 0.8em; color: #888;">{bootstrapToken.display_name}</div>
                  </td>
                  <td>{formatDate(bootstrapToken.expires_at)}</td>
                  <td><span style="color: {status.color};">{status.label}</span></td>
                  <td>
                    <button
                      type="button"
                      class="btn btn-secondary"
                      style="color: #ff5252;"
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
