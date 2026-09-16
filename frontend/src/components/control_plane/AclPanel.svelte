<script lang="ts">
  import { untrack } from 'svelte';
  import { fetchAcl, createAcl, deleteAcl, type ACL } from '../../api/control_api.js';
  import { showCustomToast } from '../../lib/toast.ts';
  import { confirmDialog } from '../../lib/dialogs.svelte.ts';
  import { msg } from './format.js';

  let acls = $state<ACL[]>([]);
  let error = $state('');

  let source = $state('');
  let target = $state('');
  let operation = $state('');
  let extra = $state('');

  $effect(() => {
    untrack(() => {
      void refresh();
    });
  });

  async function refresh(): Promise<void> {
    try {
      acls = await fetchAcl();
      error = '';
    } catch (e) {
      error = msg(e);
    }
  }

  async function onSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    try {
      await createAcl({
        source_device: source,
        target_device: target,
        operation,
        extra: extra || '',
      });
      source = '';
      target = '';
      operation = '';
      extra = '';
      await refresh();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }

  async function onDelete(aclId: string): Promise<void> {
    const confirmed = await confirmDialog({
      title: 'ACL を削除',
      message: 'この ACL を削除しますか?',
      confirmText: '削除',
    });
    if (!confirmed) return;
    try {
      await deleteAcl(aclId);
      await refresh();
    } catch (err) {
      showCustomToast(msg(err), 'error');
    }
  }
</script>

<section class="card bg-surface-100-900 mb-6 space-y-4 p-6">
  <header class="mb-4 flex flex-wrap items-center justify-between gap-2">
    <h2 class="h2">ACL</h2>
  </header>
  <form id="acl-form" class="grid gap-2 sm:grid-cols-2 lg:grid-cols-5" onsubmit={onSubmit}>
    <input
      name="source_device"
      class="input"
      placeholder="device:source-*"
      pattern="^device:.+"
      bind:value={source}
      required
    />
    <input
      name="target_device"
      class="input"
      placeholder="device:target-*"
      pattern="^device:.+"
      bind:value={target}
      required
    />
    <input name="operation" class="input" placeholder="op regex (e.g. .*)" bind:value={operation} required />
    <input name="extra" class="input" placeholder="extra (optional)" bind:value={extra} />
    <button type="submit" class="btn preset-filled-primary-500">追加</button>
  </form>
  {#if error}
    <p class="text-error-500">Error: {error}</p>
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
                onclick={() => onDelete(acl.id)}
              >
                削除
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>
