<script lang="ts">
  import { goto as navigate } from '$app/navigation';
  import { registerDevice, setToken } from '../../api/control_api.js';
  import { msg } from './format.js';

  let { onRegistered = () => {} }: { onRegistered?: () => void } = $props();

  let deviceId = $state('webui');
  let displayName = $state('WebUI');
  let bootstrapToken = $state('');
  let error = $state('');
  let busy = $state(false);

  async function onSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    error = '';
    busy = true;
    try {
      const result = await registerDevice({
        device_id: deviceId,
        display_name: displayName,
        bootstrap_token: bootstrapToken,
      });
      setToken(result.bearer_token, result.id);
      onRegistered();
      await navigate('/control/devices');
    } catch (err) {
      error = msg(err);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card bg-surface-100-900 mx-auto mt-16 max-w-[30rem] p-8">
  <h2 class="h2 mb-3">WebUI セットアップ</h2>
  <p class="mb-3 text-sm text-surface-600-400">
    この WebUI を使うには、まずサーバー側で bootstrap トークンを発行してください:
  </p>
  <pre class="pre mt-4 mb-6">portal-manage control issue-bootstrap-token \
  --device-id webui \
  --display-name "WebUI"</pre>
  <form id="bootstrap-form" class="mt-6 flex flex-col gap-3" onsubmit={onSubmit}>
    <label class="label" for="bootstrap-device-id">
      <span class="label-text">Device ID</span>
      <input id="bootstrap-device-id" name="device_id" class="input" bind:value={deviceId} required />
    </label>
    <label class="label" for="bootstrap-display-name">
      <span class="label-text">Display name</span>
      <input id="bootstrap-display-name" name="display_name" class="input" bind:value={displayName} required />
    </label>
    <label class="label" for="bootstrap-token">
      <span class="label-text">Bootstrap token</span>
      <input id="bootstrap-token" name="bootstrap_token" class="input font-mono" bind:value={bootstrapToken} required />
    </label>
    <button type="submit" class="btn preset-filled-primary-500 w-full" disabled={busy}>セットアップ</button>
    <div id="bootstrap-error" class="text-sm text-error-500">{error}</div>
  </form>
</section>
