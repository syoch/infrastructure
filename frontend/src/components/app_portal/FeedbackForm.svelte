<script lang="ts">
  import { safeURL } from '../../lib/ui.js';

  let {
    webui_url,
    sending,
    onsubmit,
  }: {
    webui_url?: string | null;
    sending: boolean;
    onsubmit: (e: SubmitEvent) => void;
  } = $props();
</script>

<section class="card bg-surface-100-900 p-6">
  <header class="mb-4"><h2 class="h4 m-0">フィードバックを送信</h2></header>
  <form id="feedback-form" class="grid gap-4" onsubmit={onsubmit}>
    <label class="label">
      <span class="label-text">種別</span>
      <select id="fb-kind" name="kind" class="select">
        <option value="feedback">フィードバック</option>
        <option value="bug">不具合</option>
        <option value="feature">要望</option>
        <option value="question">質問</option>
      </select>
    </label>
    <label class="label">
      <span class="label-text">内容 *</span>
      <textarea id="fb-body" name="body" class="textarea" rows="5" required placeholder="気づいた点や要望を書いてください"></textarea>
    </label>
    <div class="flex flex-wrap items-center gap-2">
      <button type="submit" class="btn preset-filled-primary-500" disabled={sending}>
        {sending ? '送信中…' : '送信 (エージェントに注入)'}
      </button>
      {#if webui_url}
        <a class="btn preset-tonal" href={safeURL(webui_url)} target="_blank" rel="noopener">セッションを開くだけ</a>
      {/if}
    </div>
  </form>
</section>
