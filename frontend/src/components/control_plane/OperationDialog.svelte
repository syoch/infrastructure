<script lang="ts">
  import { Dialog, Portal } from '@skeletonlabs/skeleton-svelte';
  import { issueCommand, type OperationSpec } from '../../api/control_api.js';
  import type { SchemaNode } from '../../lib/schema.svelte.ts';
  import SchemaForm from '../SchemaForm.svelte';
  import { msg } from './format.js';

  let {
    op,
    node,
    provider,
    onClose,
    onSubmitted,
  }: {
    op: OperationSpec;
    node: SchemaNode;
    provider: string;
    onClose: () => void;
    onSubmitted: () => void;
  } = $props();

  let error = $state('');
  let busy = $state(false);

  const title = $derived(op.ui_hint?.label || op.name);
  const description = $derived(op.description || `Operation: ${op.name}`);

  async function onSubmit(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    let commandParams: object;
    try {
      commandParams = (node.getValue() as object) || {};
    } catch (err) {
      error = msg(err);
      return;
    }
    busy = true;
    error = '';
    const targetId = provider.replace(/^device:/, '');
    try {
      await issueCommand({
        target_device_id: targetId,
        operation: op.id,
        params: commandParams,
      });
      onSubmitted();
    } catch (err) {
      error = msg(err);
      busy = false;
    }
  }
</script>

<Dialog
  open={true}
  aria-label={title}
  onOpenChange={(details) => {
    if (!details.open) onClose();
  }}
>
  <Portal>
    <Dialog.Backdrop class="fixed inset-0 z-[80] bg-surface-950/60" />
    <Dialog.Positioner class="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <Dialog.Content
        id="op-modal"
        data-testid="op-modal"
        class="card bg-surface-100-900 relative max-h-[90vh] w-full max-w-xl overflow-y-auto p-6 shadow-xl"
      >
        <Dialog.Title>
          {#snippet element(attributes)}
            <h2 {...attributes} id="op-modal-title" class="mb-3 text-xl font-bold">
              {title}
            </h2>
          {/snippet}
        </Dialog.Title>
        <p class="mb-4 text-sm text-surface-600-400">
          {description}
        </p>
        <form id="op-form" class="flex flex-col gap-3" onsubmit={onSubmit}>
          <div class="schema-form-body">
            <SchemaForm {node} />
          </div>
          {#if error}
            <div class="text-sm text-error-500">Error: {error}</div>
          {/if}
          <div class="mt-6 flex gap-2">
            <button type="submit" class="btn preset-filled-primary-500 flex-[2]" disabled={busy}>
              {busy ? '送信中…' : '実行'}
            </button>
            <button type="button" class="btn preset-tonal flex-1" onclick={onClose}>
              キャンセル
            </button>
          </div>
        </form>
      </Dialog.Content>
    </Dialog.Positioner>
  </Portal>
</Dialog>
