/**
 * OrderCommandPalette
 *
 * A floating command bar that slides up from the bottom of the viewport
 * whenever one or more order rows are selected in the OrderList Datagrid.
 *
 * Features:
 *  - Context-aware: only shows valid next statuses for the current selection
 *    (intersection of allowed transitions across all selected rows)
 *  - Keyboard-driven: Alt+1…Alt+5 map to the rendered transition buttons;
 *    Enter confirms; Esc steps back or clears selection
 *  - Inline two-step confirmation — no modal, no page navigation
 *  - Renders via React portal at z-index 1400 (above MUI Drawer/Sidebar)
 */
import { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom';
import {
  useListContext,
  useNotify,
  useRefresh,
  useUnselectAll,
} from 'react-admin';
import {
  Box,
  Button,
  CircularProgress,
  Chip,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import apiClient from '../lib/api/apiClient.ts';

// ─── Types ────────────────────────────────────────────────────────────────────

type OrderStatus = 'pending' | 'confirmed' | 'packing' | 'completed' | 'cancelled';

// ─── Constants ────────────────────────────────────────────────────────────────

/** Valid transitions — mirrors the backend ALLOWED_TRANSITIONS map */
const ALLOWED_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['packing', 'cancelled'],
  packing: ['completed', 'cancelled'],
  completed: ['confirmed'],  // can be walked back to confirmed
  cancelled: [],             // terminal — protected, cannot be changed
};

const STATUS_LABELS: Record<OrderStatus, string> = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  packing: 'Packing',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

const STATUS_COLORS: Record<OrderStatus, string> = {
  pending: '#FFA726',
  confirmed: '#66BB6A',
  packing: '#42A5F5',
  completed: '#4CAF50',
  cancelled: '#EF5350',
};

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Derives the list of valid target statuses for the current row selection.
 * Uses the record cache inside useListContext to read statuses without
 * a second network round-trip.
 */
export function useOrderSelection(): {
  selectedIds: (string | number)[];
  selectedStatuses: OrderStatus[];
  validTransitions: OrderStatus[];
  /** How many selected orders can actually move to a given target status */
  eligibleCount: (target: OrderStatus) => number;
  selectionCount: number;
} {
  const { selectedIds, data } = useListContext();

  const selectedStatuses: OrderStatus[] = [];
  for (const id of selectedIds) {
    const record = data?.find((r: { id: string | number }) => r.id === id);
    if (record?.status) {
      selectedStatuses.push(record.status as OrderStatus);
    }
  }

  // Union: show a target if at least one selected order can move to it
  const displayOrder: OrderStatus[] = [
    'pending',
    'confirmed',
    'packing',
    'completed',
    'cancelled',
  ];

  const union = new Set<OrderStatus>();
  for (const s of selectedStatuses) {
    for (const t of ALLOWED_TRANSITIONS[s] ?? []) {
      union.add(t);
    }
  }
  const validTransitions = displayOrder.filter((s) => union.has(s));

  const eligibleCount = (target: OrderStatus) =>
    selectedStatuses.filter((s) =>
      (ALLOWED_TRANSITIONS[s] ?? []).includes(target)
    ).length;

  return {
    selectedIds,
    selectedStatuses,
    validTransitions,
    eligibleCount,
    selectionCount: selectedIds.length,
  };
}

// ─── Component ────────────────────────────────────────────────────────────────

export const OrderCommandPalette = () => {
  const { selectedIds, selectedStatuses, validTransitions, eligibleCount, selectionCount } =
    useOrderSelection();
  const notify = useNotify();
  const refresh = useRefresh();
  const unselectAll = useUnselectAll('orders');

  const allCancelled =
    selectionCount > 0 && selectedStatuses.every((s) => s === 'cancelled');

  // "confirm" sub-step state
  const [pendingStatus, setPendingStatus] = useState<OrderStatus | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Slide-in animation
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (selectionCount > 0) {
      setVisible(true);
    } else {
      setVisible(false);
      setPendingStatus(null);
    }
  }, [selectionCount]);

  // ── Keyboard shortcuts ──────────────────────────────────────────────────
  const validTransitionsRef = useRef(validTransitions);
  validTransitionsRef.current = validTransitions;
  const pendingStatusRef = useRef(pendingStatus);
  pendingStatusRef.current = pendingStatus;

  useEffect(() => {
    if (selectionCount === 0) return;

    const onKeyDown = (e: KeyboardEvent) => {
      // Alt+digit → choose a transition
      if (e.altKey && !e.ctrlKey && !e.metaKey) {
        const digit = parseInt(e.key, 10);
        if (!isNaN(digit) && digit >= 1 && digit <= 5) {
          const transition = validTransitionsRef.current[digit - 1];
          if (transition) {
            e.preventDefault();
            setPendingStatus(transition);
          }
        }
      }

      // Enter → confirm pending transition
      if (e.key === 'Enter' && pendingStatusRef.current) {
        e.preventDefault();
        executeUpdate(pendingStatusRef.current);
      }

      // Escape → step back or dismiss
      if (e.key === 'Escape') {
        e.preventDefault();
        if (pendingStatusRef.current) {
          setPendingStatus(null);
        } else {
          unselectAll();
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectionCount]);

  // ── API call ───────────────────────────────────────────────────────────
  const executeUpdate = async (newStatus: OrderStatus) => {
    setIsSubmitting(true);
    try {
      const res = await apiClient.post('/orders/bulk_update_status/', {
        order_ids: selectedIds,
        new_status: newStatus,
      });
      const { updated_count, skipped_count } = res.data as {
        updated_count: number;
        skipped_count: number;
      };
      const msg =
        skipped_count > 0
          ? `Updated ${updated_count} order(s) to ${STATUS_LABELS[newStatus]}. ${skipped_count} skipped (invalid transition).`
          : `Updated ${updated_count} order(s) to ${STATUS_LABELS[newStatus]}.`;
      notify(msg, { type: 'success' });
      setPendingStatus(null);
      unselectAll();
      refresh();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error ?? 'Bulk update failed.';
      notify(msg, { type: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (selectionCount === 0) return null;

  // ── Render (via portal) ────────────────────────────────────────────────
  const bar = (
    <Box
      role="toolbar"
      aria-label="Bulk order status update"
      sx={{
        position: 'fixed',
        bottom: 24,
        left: '50%',
        transform: visible
          ? 'translateX(-50%) translateY(0)'
          : 'translateX(-50%) translateY(120px)',
        transition: 'transform 200ms ease-in-out',
        zIndex: 1400,
        bgcolor: '#1e1e2e',
        color: '#fff',
        borderRadius: 2,
        boxShadow: 8,
        px: 3,
        py: 1.5,
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        minWidth: 360,
        maxWidth: '90vw',
      }}
    >
      {/* ── Selection count ── */}
      <Chip
        label={`${selectionCount} selected`}
        size="small"
        sx={{ bgcolor: '#3d3d5c', color: '#fff', fontWeight: 600 }}
      />

      {!pendingStatus ? (
        // ── Step 1: choose target status ──────────────────────────────
        <>
          {validTransitions.length > 0 ? (
            <>
              <Typography variant="body2" sx={{ opacity: 0.7, flexShrink: 0 }}>
                Move to →
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {validTransitions.map((s, i) => {
                  const n = eligibleCount(s);
                  const allEligible = n === selectionCount;
                  return (
                    <Button
                      key={s}
                      size="small"
                      variant="contained"
                      onClick={() => setPendingStatus(s)}
                      title={`Alt+${i + 1}`}
                      sx={{
                        bgcolor: STATUS_COLORS[s],
                        color: '#fff',
                        fontWeight: 600,
                        textTransform: 'none',
                        fontSize: '0.8rem',
                        '&:hover': { bgcolor: STATUS_COLORS[s], filter: 'brightness(1.15)' },
                      }}
                    >
                      {STATUS_LABELS[s]}
                      {!allEligible && (
                        <Typography
                          component="span"
                          sx={{ ml: 0.5, opacity: 0.8, fontSize: '0.7rem' }}
                        >
                          ({n}/{selectionCount})
                        </Typography>
                      )}
                      <Typography
                        component="span"
                        sx={{ ml: 0.75, opacity: 0.65, fontSize: '0.7rem' }}
                      >
                        Alt+{i + 1}
                      </Typography>
                    </Button>
                  );
                })}
              </Box>
            </>
          ) : allCancelled ? (
            <Typography variant="body2" sx={{ opacity: 0.6 }}>
              🔒 Cancelled orders are protected and cannot be changed.
            </Typography>
          ) : (
            <Typography variant="body2" sx={{ opacity: 0.6 }}>
              No valid transitions for this selection.
            </Typography>
          )}

          {/* Dismiss */}
          <Button
            size="small"
            onClick={() => unselectAll()}
            title="Esc"
            sx={{ color: '#aaa', ml: 'auto', minWidth: 0, p: 0.5 }}
          >
            <CloseIcon fontSize="small" />
          </Button>
        </>
      ) : (
        // ── Step 2: inline confirmation ───────────────────────────────
        <>
          <ArrowForwardIcon sx={{ opacity: 0.6, fontSize: '1rem' }} />
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
              Move {eligibleCount(pendingStatus)} order{eligibleCount(pendingStatus) !== 1 ? 's' : ''} →{' '}
              <Box component="span" sx={{ color: STATUS_COLORS[pendingStatus], fontWeight: 700 }}>
                {STATUS_LABELS[pendingStatus]}
              </Box>
              {eligibleCount(pendingStatus) < selectionCount && (
                <Typography
                  component="span"
                  variant="caption"
                  sx={{ ml: 1, opacity: 0.6 }}
                >
                  ({selectionCount - eligibleCount(pendingStatus)} will be skipped)
                </Typography>
              )}
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', gap: 1, ml: 'auto' }}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => setPendingStatus(null)}
              disabled={isSubmitting}
              title="Esc"
              sx={{ color: '#aaa', borderColor: '#555', textTransform: 'none' }}
            >
              Cancel
            </Button>
            <Button
              size="small"
              variant="contained"
              color="success"
              onClick={() => executeUpdate(pendingStatus)}
              disabled={isSubmitting}
              title="Enter"
              startIcon={
                isSubmitting ? (
                  <CircularProgress size={14} color="inherit" />
                ) : (
                  <CheckIcon />
                )
              }
              sx={{ textTransform: 'none', fontWeight: 600 }}
            >
              {isSubmitting ? 'Updating…' : 'Yes, update ↵'}
            </Button>
          </Box>
        </>
      )}
    </Box>
  );

  return ReactDOM.createPortal(bar, document.body);
};
