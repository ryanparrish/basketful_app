/**
 * Stock movement helpers (Issue #144), shared by the React admin screens
 * and their tests.
 */
export const STOCK_MOVEMENT_KINDS = [
  { id: 'received', name: 'Received / Purchase' },
  { id: 'donation', name: 'Donation' },
  { id: 'spoilage', name: 'Spoilage / Removal' },
  { id: 'correction', name: 'Correction' },
];

// Kinds that only add stock / only remove it. Corrections go either way.
// Mirrors StockMovement.INCOMING_KINDS / OUTGOING_KINDS on the server, which
// is the real check; this just gives instant feedback in the form.
const INCOMING_KINDS = new Set(['received', 'donation']);
const OUTGOING_KINDS = new Set(['spoilage']);

/**
 * Field validator for the quantity input, matching the server's rules
 * (react-admin calls it with the field value and all form values).
 * Returns an error message, or undefined when the value is fine.
 */
export const validateQuantityChange = (
  value: unknown,
  values: Record<string, unknown> = {},
): string | undefined => {
  if (value === undefined || value === null || value === '') {
    return undefined; // `required()` on the input reports this
  }
  const change = Number(value);
  const kind = values.kind;
  if (!Number.isInteger(change)) {
    return 'Use a whole number.';
  }
  if (change === 0) {
    return 'Use a positive or negative number, not zero.';
  }
  if (typeof kind === 'string' && INCOMING_KINDS.has(kind) && change < 0) {
    return 'This kind adds stock, so the quantity must be positive. Use Spoilage / Removal or Correction to take stock out.';
  }
  if (typeof kind === 'string' && OUTGOING_KINDS.has(kind) && change > 0) {
    return 'Spoilage / Removal takes stock out, so use a negative number (for example -5).';
  }
  return undefined;
};

/**
 * Turn an API error into the message the server actually sent
 * (e.g. "This movement would take Rice below zero ..."), instead of
 * axios's generic "Request failed with status code 400".
 */
export const stockMovementErrorMessage = (error: unknown): string => {
  const err = error as { response?: { data?: unknown }; message?: string };
  const data = err?.response?.data;
  if (data && typeof data === 'object') {
    const parts = Object.values(data as Record<string, unknown>).map((msgs) =>
      Array.isArray(msgs) ? msgs.join(' ') : String(msgs)
    );
    if (parts.length) return parts.join(' ');
  }
  if (typeof data === 'string' && data) return data;
  return err?.message || 'Could not record the stock movement.';
};
