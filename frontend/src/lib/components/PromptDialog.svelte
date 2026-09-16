<script lang="ts">
  import { untrack } from 'svelte';
  import { Dialog, Portal } from '@skeletonlabs/skeleton-svelte';
  import { getPromptRequest, resolvePrompt } from '$lib/dialogs.svelte.ts';

  const request = $derived(getPromptRequest());

  let value = $state('');

  $effect(() => {
    const current = request;
    if (!current) return;
    untrack(() => {
      value = current.defaultValue ?? '';
    });
  });

  function submit(e: SubmitEvent): void {
    e.preventDefault();
    resolvePrompt(value);
  }
</script>

{#if request}
  {#key request.id}
    <Dialog
      open={true}
      role="dialog"
      closeOnInteractOutside={false}
      onOpenChange={(details) => {
        if (!details.open) resolvePrompt(null);
      }}
    >
      <Portal>
        <Dialog.Backdrop class="fixed inset-0 z-[90] bg-surface-950/60" />
        <Dialog.Positioner class="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <Dialog.Content
            data-testid="prompt-dialog"
            class="card bg-surface-100-900 w-full max-w-md space-y-4 p-6 shadow-xl"
          >
            <Dialog.Title class="text-lg font-bold">
              {request.title ?? '入力'}
            </Dialog.Title>
            {#if request.message}
              <Dialog.Description class="text-sm whitespace-pre-line text-surface-700-300">
                {request.message}
              </Dialog.Description>
            {/if}
            <form class="space-y-4" onsubmit={submit}>
              <label class="label" for="prompt-dialog-field">
                <span class="label-text">{request.label ?? ''}</span>
                <input
                  id="prompt-dialog-field"
                  class="input"
                  data-testid="prompt-dialog-input"
                  placeholder={request.placeholder ?? ''}
                  bind:value
                />
              </label>
              <footer class="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  class="btn preset-tonal"
                  data-testid="prompt-dialog-cancel"
                  onclick={() => resolvePrompt(null)}
                >
                  {request.cancelText ?? 'キャンセル'}
                </button>
                <button
                  type="submit"
                  class="btn preset-filled-primary-500"
                  data-testid="prompt-dialog-confirm"
                >
                  {request.confirmText ?? 'OK'}
                </button>
              </footer>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog>
  {/key}
{/if}
