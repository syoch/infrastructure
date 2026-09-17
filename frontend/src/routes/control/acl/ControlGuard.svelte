<script lang="ts">
  let { deviceId = '' }: { deviceId?: string } = $props();
</script>

<div data-testid="control-guard" class="card bg-surface-100-900 space-y-4 p-10 text-center text-surface-600-400">
  <p>
    この画面は admin 専用です。現在のデバイス <code>{deviceId || '(unknown)'}</code> には admin 権限がありません。
  </p>
  <a href="/control/devices" class="btn preset-filled-primary-500">Devices に戻る</a>
</div>
