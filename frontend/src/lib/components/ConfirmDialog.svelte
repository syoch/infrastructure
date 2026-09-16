<script lang="ts">
  import { Dialog, Portal } from '@skeletonlabs/skeleton-svelte';
  import { getConfirmRequest, resolveConfirm } from '$lib/dialogs.svelte.ts';

  const request = $derived(getConfirmRequest());
</script>

{#if request}
  {#key request.id}
    <Dialog
      open={true}
      role="alertdialog"
      closeOnInteractOutside={false}
      onOpenChange={(details) => {
        if (!details.open) resolveConfirm(false);
      }}
    >
      <Portal>
        <Dialog.Backdrop class="fixed inset-0 z-[90] bg-surface-950/60" />
        <Dialog.Positioner class="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <Dialog.Content
            data-testid="confirm-dialog"
            class="card bg-surface-100-900 w-full max-w-md space-y-4 p-6 shadow-xl"
          >
            <Dialog.Title class="text-lg font-bold">
              {request.title ?? '確認'}
            </Dialog.Title>
            {#if request.message}
              <Dialog.Description class="text-sm whitespace-pre-line text-surface-700-300">
                {request.message}
              </Dialog.Description>
            {/if}
            <footer class="flex justify-end gap-2 pt-2">
              <button
                type="button"
                class="btn preset-tonal"
                data-testid="confirm-dialog-cancel"
                onclick={() => resolveConfirm(false)}
              >
                {request.cancelText ?? 'キャンセル'}
              </button>
              <button
                type="button"
                class="btn preset-filled-primary-500"
                data-testid="confirm-dialog-confirm"
                onclick={() => resolveConfirm(true)}
              >
                {request.confirmText ?? 'OK'}
              </button>
            </footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog>
  {/key}
{/if}
