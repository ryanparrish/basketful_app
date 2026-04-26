import type { WindowStatus } from './types';

export const getCsrfToken = (): string =>
  document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] ?? '';

export const STATUS_META: Record<
  WindowStatus,
  { label: string; color: 'success' | 'warning' | 'error' | 'default' | 'info' }
> = {
  open: { label: 'OPEN', color: 'success' },
  closed: { label: 'CLOSED', color: 'default' },
  force_open: { label: 'FORCE OPEN', color: 'warning' },
  force_closed: { label: 'FORCE CLOSED', color: 'error' },
  disabled: { label: 'DISABLED', color: 'info' },
  no_schedule: { label: 'NO SCHEDULE', color: 'default' },
};

export const fmt = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
