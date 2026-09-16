import { createToaster } from '@skeletonlabs/skeleton-svelte';

export type ToastType = 'info' | 'success' | 'error' | 'warning';

/**
 * Shared Skeleton/Zag toaster singleton. The matching `<Toast.Group>` is
 * rendered once in `src/routes/+layout.svelte`.
 */
export const toaster = createToaster({
  placement: 'bottom-end',
  overlap: true,
  gap: 12,
});

export function showToast(
  message: string,
  type: ToastType = 'info',
  duration = 3000
): void {
  toaster.create({
    type,
    title: message,
    duration,
    closable: true,
  });
}

/**
 * Legacy alias kept so existing call sites (`showCustomToast`) keep working.
 */
export function showCustomToast(
  message: string,
  type: ToastType = 'info',
  duration = 3000
): void {
  showToast(message, type, duration);
}
