import type { BootstrapToken } from '../../api/control_api.js';

export function msg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function wsBadgeClass(state: string | undefined): string {
  if (state === 'online') return 'badge preset-filled-success-500';
  if (state === 'offline') return 'badge preset-tonal-surface';
  return 'badge preset-filled-warning-500';
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  return value.toString().replace('T', ' ').substring(0, 19);
}

export function tokenStatus(t: BootstrapToken): { label: string; cls: string } {
  if (t.consumed_at) return { label: 'Consumed', cls: 'badge preset-tonal-surface' };
  if (new Date(t.expires_at) < new Date()) return { label: 'Expired', cls: 'badge preset-filled-error-500' };
  return { label: 'Pending', cls: 'badge preset-filled-success-500' };
}

export function statusBadgeClass(status: string): string {
  const cls: Record<string, string> = {
    pending: 'badge preset-filled-warning-500',
    claimed: 'badge preset-filled-primary-500',
    running: 'badge preset-filled-primary-500',
    succeeded: 'badge preset-filled-success-500',
    failed: 'badge preset-filled-error-500',
    timeout: 'badge preset-tonal-surface',
    cancelled: 'badge preset-tonal-surface',
  };
  return cls[status] || 'badge preset-tonal-surface';
}
