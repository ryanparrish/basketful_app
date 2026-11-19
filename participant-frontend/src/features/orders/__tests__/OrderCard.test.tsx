/**
 * #134: the order status chip covers exactly the statuses the backend
 * produces (Order.status choices), each with a translated label.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OrderCard } from '../OrderCard';
import type { OrderListItem } from '../../../shared/types/api';
import en from '../../../locales/en.json';
import es from '../../../locales/es.json';

// Mirrors apps/orders/models.py Order.status choices
const BACKEND_ORDER_STATUSES = ['pending', 'confirmed', 'packing', 'completed', 'cancelled'];

const orderWithStatus = (status: string): OrderListItem => ({
  id: 1,
  order_number: 'ORD-001',
  status,
  order_date: '2026-05-01T10:00:00Z',
  created_at: '2026-05-01T10:00:00Z',
  total_price: 25.0,
  item_count: 0,
  items: [],
});

describe('OrderCard status chip', () => {
  it.each(BACKEND_ORDER_STATUSES)('shows a translated label for %s, not the raw status code', (status) => {
    render(<OrderCard order={orderWithStatus(status)} />);

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
