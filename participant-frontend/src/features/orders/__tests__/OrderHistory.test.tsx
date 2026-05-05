/**
 * Tests for OrderHistory — BEH-069, BEH-210, BEH-211, BEH-212
 *
 * Key security contract (BEH-069):
 *   The participant frontend must NEVER add a participant ID or account filter
 *   to the orders request. The backend enforces row-level scoping via the
 *   authenticated session cookie — the frontend must not bypass or widen that
 *   scope by passing extra query params.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { OrderHistory } from '../OrderHistory';
import type { OrderListItem } from '../../../shared/types/api';

// ---------------------------------------------------------------------------
// Mock the endpoints module — we control what getOrders returns per test
// ---------------------------------------------------------------------------
vi.mock('../../../shared/api/endpoints', () => ({
  getOrders: vi.fn(),
}));

import { getOrders } from '../../../shared/api/endpoints';
const mockGetOrders = vi.mocked(getOrders);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const ORDER_STUB: OrderListItem = {
  id: 1,
  order_number: 'ORD-001',
  status: 'confirmed',
  order_date: '2026-05-01T10:00:00Z',
  created_at: '2026-05-01T10:00:00Z',
  total_price: 25.00,
  item_count: 2,
  items: [],
};

function renderOrderHistory() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <OrderHistory />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('OrderHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // BEH-069 — CRITICAL: participant isolation
  describe('BEH-069 — order request scope', () => {
    it('calls getOrders exactly once and passes no participant_id or account override', async () => {
      mockGetOrders.mockResolvedValue([ORDER_STUB]);

      renderOrderHistory();

      await waitFor(() => expect(mockGetOrders).toHaveBeenCalledTimes(1));

      // TanStack Query passes a QueryFunctionContext as the first arg.
      // The security contract is that getOrders must NOT receive any extra
      // argument that could widen scope (e.g. participant_id, account).
      // Exactly one call, and only the standard context object — no second arg.
      const callArgs = mockGetOrders.mock.calls[0] as unknown[];
      expect(callArgs).toHaveLength(1); // only the QueryFunctionContext, nothing else

      const context = callArgs[0] as Record<string, unknown>;
      // No participant_id or account param sneaking in via the context
      expect(context).not.toHaveProperty('participant_id');
      expect(context).not.toHaveProperty('account');
    });
  });

  // BEH-210 — renders a card per order
  describe('BEH-210 — renders returned orders', () => {
    it('displays one OrderCard for each order returned by the API', async () => {
      const orders = [
        { ...ORDER_STUB, id: 1 },
        { ...ORDER_STUB, id: 2 },
        { ...ORDER_STUB, id: 3 },
      ];
      mockGetOrders.mockResolvedValue(orders);

      renderOrderHistory();

      // Each OrderCard shows the status chip — confirmed appears 3 times
      await waitFor(() => {
        const chips = screen.getAllByText('Confirmed');
        expect(chips).toHaveLength(3);
      });
    });
  });

  // BEH-211 — empty state
  describe('BEH-211 — empty state', () => {
    it('shows empty-state message when API returns zero orders', async () => {
      mockGetOrders.mockResolvedValue([]);

      renderOrderHistory();

      await waitFor(() => {
        expect(screen.getByText(/no orders yet/i)).toBeInTheDocument();
      });
    });
  });

  // BEH-212 — error state
  describe('BEH-212 — error state', () => {
    it('shows error alert when the API call rejects', async () => {
      mockGetOrders.mockRejectedValue(new Error('Network Error'));

      renderOrderHistory();

      await waitFor(() => {
        expect(screen.getByText(/failed to load orders/i)).toBeInTheDocument();
      });
    });
  });
});
