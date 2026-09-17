<script lang="ts">
  let { onsubmit }: { onsubmit: (e: SubmitEvent) => void } = $props();
</script>

<form
  id="app-register-form"
  class="card mb-6 grid gap-4 bg-surface-50-950 p-4 sm:grid-cols-2"
  onsubmit={onsubmit}
>
  <label class="label">
    <span class="label-text">アプリ名 *</span>
    <input id="rg-name" name="name" class="input" required>
  </label>
  <label class="label">
    <span class="label-text">説明</span>
    <input id="rg-description" name="description" class="input">
  </label>
  <label class="label">
    <span class="label-text">公開 URL</span>
    <input id="rg-url" name="url" class="input" placeholder="http://...">
  </label>
  <label class="label">
    <span class="label-text">プロジェクトディレクトリ *</span>
    <input id="rg-dir" name="project_directory" class="input" placeholder="/home/syoch/work/..." required>
  </label>
  <label class="label">
    <span class="label-text">OpenCode セッション ID *</span>
    <input id="rg-session" name="opencode_session_id" class="input" placeholder="ses_..." required>
  </label>
  <label class="label">
    <span class="label-text">タグ (カンマ区切り)</span>
    <input id="rg-tags" name="tags" class="input">
  </label>
  <div class="sm:col-span-2">
    <button type="submit" class="btn preset-filled-primary-500">登録</button>
  </div>
</form>
