/**
 * Shared primitive components for all Log resources.
 * Color-coded badges that mirror the Django admin's format_html indicators.
 */
import { Chip } from '@mui/material';
import { useRecordContext } from 'react-admin';

// ─── Log Type Badge (INFO / WARNING / ERROR) ─────────────────────────────────

const LOG_TYPE_COLOR: Record<string, 'default' | 'info' | 'warning' | 'error'> = {
  INFO: 'info',
  WARNING: 'warning',
  ERROR: 'error',
};

export const LogTypeBadge = () => {
  const record = useRecordContext();
  if (!record) return null;
  const value: string = record.log_type ?? 'INFO';
  return (
    <Chip
      label={value}
      color={LOG_TYPE_COLOR[value] ?? 'default'}
      size="small"
      variant="outlined"
    />
  );
};
LogTypeBadge.displayName = 'LogTypeBadge';

// ─── Email Status Chip (sent / failed) ────────────────────────────────────────

export const EmailStatusChip = () => {
  const record = useRecordContext();
  if (!record) return null;
  const sent = record.status === 'sent';
  return (
    <Chip
      label={sent ? '✓ Sent' : '✗ Failed'}
      color={sent ? 'success' : 'error'}
      size="small"
    />
  );
};
EmailStatusChip.displayName = 'EmailStatusChip';

// ─── Delivery Status Chip (Mailgun delivery result) ───────────────────────────

const DELIVERY_STATUS_COLOR: Record<string, 'default' | 'success' | 'error' | 'warning' | 'info'> = {
  delivered:    'success',
  bounced:      'error',
  complained:   'warning',
  unsubscribed: 'default',
  failed:       'error',
  unknown:      'default',
};

const DELIVERY_STATUS_LABEL: Record<string, string> = {
  delivered:    '✓ Delivered',
  bounced:      '✗ Bounced',
  complained:   '⚠ Complained',
  unsubscribed: '− Unsubscribed',
  failed:       '✗ Failed',
  unknown:      '… Pending',
};

export const DeliveryStatusChip = () => {
  const record = useRecordContext();
  if (!record) return null;
  const ds: string = record.delivery_status ?? 'unknown';
  return (
    <Chip
      label={DELIVERY_STATUS_LABEL[ds] ?? ds}
      color={DELIVERY_STATUS_COLOR[ds] ?? 'default'}
      size="small"
      variant={ds === 'unknown' ? 'outlined' : 'filled'}
    />
  );
};
DeliveryStatusChip.displayName = 'DeliveryStatusChip';

// ─── Login Action Badge ───────────────────────────────────────────────────────

const ACTION_COLOR: Record<string, 'success' | 'default' | 'error'> = {
  login: 'success',
  logout: 'default',
  failed_login: 'error',
};

const ACTION_LABEL: Record<string, string> = {
  login: '→ Login',
  logout: '← Logout',
  failed_login: '✗ Failed',
};

export const LoginActionBadge = () => {
  const record = useRecordContext();
  if (!record) return null;
  const action: string = record.action ?? '';
  return (
    <Chip
      label={ACTION_LABEL[action] ?? action}
      color={ACTION_COLOR[action] ?? 'default'}
      size="small"
    />
  );
};
LoginActionBadge.displayName = 'LoginActionBadge';

// ─── Grace Proceeded Chip ────────────────────────────────────────────────────

export const ProceededChip = () => {
  const record = useRecordContext();
  if (!record) return null;
  return record.proceeded ? (
    <Chip label="✓ Proceeded" color="success" size="small" />
  ) : (
    <Chip label="Reviewed Only" color="default" size="small" variant="outlined" />
  );
};
ProceededChip.displayName = 'ProceededChip';

// ─── Active / Inactive Chip ───────────────────────────────────────────────────

export const ActiveChip = () => {
  const record = useRecordContext();
  if (!record) return null;
  return record.is_active ? (
    <Chip label="Active" color="success" size="small" />
  ) : (
    <Chip label="Inactive" color="default" size="small" variant="outlined" />
  );
};
ActiveChip.displayName = 'ActiveChip';
