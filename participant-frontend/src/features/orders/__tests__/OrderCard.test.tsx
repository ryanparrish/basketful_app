/**
 * OrderCard
 * - #134: the status chip covers exactly the statuses the backend produces
 *   (Order.status choices), each with a translated label.
 * - #129: the summary comes from the list's item totals, and the order's
 *   items are loaded only when the card is expanded.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { OrderCard } from '../OrderCard';
import type { Order, OrderListItem } from '../../../shared/types/api';
import en from '../../../locales/en.json';
import es from '../../../locales/es.json';

vi.mock('../../../shared/api/endpoints', () => ({
  getOrder: vi.fn(),
}));

import { getOrder } from '../../../shared/api/endpoints';
const mockGetOrder = vi.mocked(getOrder);

// Mirrors apps/orders/models.py Order.status choices
const BACKEND_ORDER_STATUSES = ['pending', 'confirmed', 'packing', 'completed', 'cancelled'];

const listOrder = (overrides: Partial<OrderListItem> = {}): OrderListItem => ({
  id: 1,
  order_number: 'ORD-001',
  status: 'completed',
  order_date: '2026-05-01T10:00:00Z',
  created_at: '2026-05-01T10:00:00Z',
  total_price: 25.0,
  item_count: 2,
  total_quantity: 5,
  ...overrides,
});

const orderDetail: Order = {
  id: 1,
  order_number: 'ORD-001',
  order_date: '2026-05-01T10:00:00Z',
  status: 'completed',
  items: [
    { id: 11, product: 7, product_id: 7, product_name: 'Rice', quantity: 2, price: 3.25, total: 6.5 },
    { id: 12, product: 8, product_id: 8, product_name: 'Beans', quantity: 3, price: 1.1, total: 3.3 },
  ],
  total_price: 9.8,
  total: 9.8,
  created_at: '2026-05-01T10:00:00Z',
};

const renderCard = (order: OrderListItem) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OrderCard order={order} />
    </QueryClientProvider>
  );
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('OrderCard status chip', () => {
  it.each(BACKEND_ORDER_STATUSES)('shows a translated label for %s, not the raw status code', (status) => {
    renderCard(listOrder({ status }));

    const label = en.orders.status[status as keyof typeof en.orders.status];
    expect(label).toBeDefined();
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.queryByText(status)).not.toBeInTheDocument();
  });
});

describe('orders.status locale labels', () => {
  it.each([
    ['en', en],
    ['es', es],
  ])('%s has a label for exactly the backend order statuses', (_language, catalog) => {
    expect(Object.keys(catalog.orders.status).sort()).toEqual([...BACKEND_ORDER_STATUSES].sort());
  });
});

describe('OrderCard items', () => {
  it('summarises the order from the list item totals without loading the order', () => {
    renderCard(listOrder({ item_count: 2, total_quantity: 5 }));

    expect(screen.getByText('2 items (5 total)')).toBeInTheDocument();
    expect(mockGetOrder).not.toHaveBeenCalled();
  });

  it('loads and lists the order items when the card is expanded', async () => {
    mockGetOrder.mockResolvedValue(orderDetail);
    renderCard(listOrder());

    await userEvent.click(screen.getByRole('button', { name: en.orders.showDetails }));

    expect(await screen.findByText('Rice')).toBeInTheDocument();
    expect(screen.getByText('Beans')).toBeInTheDocument();
    expect(mockGetOrder).toHaveBeenCalledWith(1);
  });

  it('shows an error when the order items cannot be loaded', async () => {
    mockGetOrder.mockRejectedValue(new Error('network'));
    renderCard(listOrder());

    await userEvent.click(screen.getByRole('button', { name: en.orders.showDetails }));

    expect(await screen.findByText(en.orders.detailsLoadFailed)).toBeInTheDocument();
  });
});
