/**
 * Canonical order status definitions for the admin frontend.
 *
 * Single source of truth for status colors, labels, and MUI chip variants.
 * Import from here instead of defining local copies in each component.
 */

export type OrderStatus = 'pending' | 'confirmed' | 'packing' | 'completed' | 'cancelled';

/** Hex background colors — used for status chips, palette buttons, and charts. */
export const ORDER_STATUS_COLORS: Record<OrderStatus, string> = {
  pending:   '#FFA726',  // amber
  confirmed: '#43A047',  // green
  packing:   '#42A5F5',  // blue
  completed: '#8E24AA',  // purple
  cancelled: '#EF5350',  // red
};

/** Display labels */
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  pending:   'Pending',
  confirmed: 'Confirmed',
  packing:   'Packing',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

/**
 * MUI Chip `color` prop variants — used where a semantic MUI color token is
 * needed instead of a raw hex value (e.g. filter chips).
 */
export const ORDER_STATUS_MUI_COLORS: Record<OrderStatus, 'warning' | 'success' | 'info' | 'secondary' | 'error'> = {
  pending:   'warning',
  confirmed: 'success',
  packing:   'info',
  completed: 'secondary',
  cancelled: 'error',
};

/** Fallback for unknown / unmapped status values */
export const STATUS_COLOR_FALLBACK = '#9E9E9E';

/** Convenience helper — safe for runtime strings that may not be a known status */
export function getOrderStatusColor(status: string): string {
  return ORDER_STATUS_COLORS[status as OrderStatus] ?? STATUS_COLOR_FALLBACK;
}
