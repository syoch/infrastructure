<script lang="ts">
  import { untrack } from 'svelte';
  import { Switch } from '@skeletonlabs/skeleton-svelte';
  import { fetchDevices, setAdmin, deleteDevice, type Device } from '../../api/control_api.js';
  import { showCustomToast } from '../../lib/toast.ts';
  import { confirmDialog } from '../../lib/dialogs.svelte.ts';
  import { msg, wsBadgeClass, formatDate } from './format.js';

  let { me }: { me: Device } = $props();

  let devices = $state<Device[]>([]);
  let error = $state('');

  const isAdmin = $derived(me.is_first_webui_device === true);

  $effect(() => {
    untrack(() => {
      void refresh();
    });
  });

  async function refresh(): Promise<void> {
    try {
      devices = await fetchDevices();
      error = '';
    } catch (e) {
      error = msg(e);
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
      await refresh();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  async function onDelete(device: Device): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'デバイスを削除',
      message: `Device ${device.id} を削除しますか?`,
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteDevice(device.id);
      await refresh();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }
</script>

<section class="card bg-surface-100-900 mb-6 space-y-4 p-6">
  <header class="mb-4 flex flex-wrap items-center justify-between gap-2">
    <h2 class="h2">Devices</h2>
    <span class="font-mono text-sm text-surface-600-400">{me.id}{isAdmin ? ' (admin)' : ''}</span>
  </header>
  <div id="devices-list" class="card bg-surface-100-900 overflow-x-auto">
    {#if error}
      <p class="p-4 text-error-500">Error: {error}</p>
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
                <span class={wsBadgeClass(device.ws_state)}>
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
                    onclick={() => onDelete(device)}
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
