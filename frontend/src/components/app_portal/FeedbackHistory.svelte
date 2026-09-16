<script lang="ts">
  import type { AppFeedback } from '../../api/app_portal_api.js';
  import { safeURL } from '../../lib/ui.js';

  let {
    feedback,
    onRefresh,
  }: {
    feedback: AppFeedback[];
    onRefresh: (id: string) => void;
  } = $props();

  function statusClass(status: string): string {
    return status === 'delivered'
      ? 'preset-filled-success-500'
      : status === 'failed'
        ? 'preset-filled-error-500'
        : 'preset-filled-warning-500';
  }

  function fmt(dt: string | null | undefined): string {
    return (dt || '').replace('T', ' ').substring(0, 19);
  }
</script>

<section class="card bg-surface-100-900 p-6">
  <header class="mb-4"><h2 class="h4 m-0">フィードバック履歴</h2></header>
  <div id="feedback-history" class="table-wrap">
    {#if feedback.length === 0}
      <p class="text-surface-600-400">まだフィードバックはありません。</p>
    {:else}
      <table class="table">
        <thead><tr><th>日時</th><th>種別</th><th>状態</th><th>内容</th><th></th></tr></thead>
        <tbody>
          {#each feedback as fb (fb.id)}
            <tr>
              <td>{fmt(fb.created_at)}</td>
              <td>{fb.kind}</td>
              <td><span class="badge {statusClass(fb.status)}">{fb.status}</span></td>
              <td>{fb.body.substring(0, 80)}</td>
              <td class="whitespace-nowrap">
                {#if fb.webui_url}
                  <a class="anchor" href={safeURL(fb.webui_url)} target="_blank" rel="noopener">開く</a>
                {/if}
                {#if fb.status === 'pending'}
                  <button class="btn btn-sm preset-tonal" onclick={() => onRefresh(fb.id)}>更新</button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</section>
