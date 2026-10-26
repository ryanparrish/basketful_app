/**
 * Guard for the phone layout. The mobile cart entry point once vanished
 * silently (Refine migration dropped BottomNavigation; header hid its cart
 * icon on mobile; sider renders nothing on mobile). These run in CI
 * (`npx vitest run`) so that can't happen again unnoticed.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Balances } from '../../../shared/types/api';

let isMobile = true;

vi.mock('@mui/material', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@mui/material')>()),
  useMediaQuery: () => isMobile,
}));

// Refine's ThemedLayout needs a full Refine context; a passthrough that still
// renders the Sider slot is enough to test what AppLayout itself decides.
vi.mock('@refinedev/mui', () => ({
  ThemedLayout: ({ Sider, children }: { Sider: React.FC; children: React.ReactNode }) => (
    <div>
      <Sider />
      <main>{children}</main>
    </div>
  ),
}));

vi.mock('../CustomHeader', () => ({
  CustomHeader: ({ onCartClick }: { onCartClick: () => void }) => (
    <button onClick={onCartClick}>Open cart</button>
  ),
}));

vi.mock('../CustomSider', () => ({
  CustomSider: () => (isMobile ? null : <nav>sider</nav>),
}));

vi.mock('../../../features/cart', () => ({
  CartDrawer: ({ open }: { open: boolean }) => (open ? <div>cart drawer open</div> : null),
}));

const balances: Balances = {
  available_balance: 40,
  hygiene_balance: 0,
  go_fresh_balance: 10,
  full_balance: 40,
};

vi.mock('../../../providers/ValidationContext', () => ({
  useValidation: () => ({ balances }),
}));

vi.mock('../../../providers/CartProvider', () => ({
  useCartContext: () => ({
    totalItems: 2,
    cartTotal: 5,
    items: [
      { id: 'product-1', productId: 1, name: 'Beans', price: 1.5, quantity: 1, budget: 'food', available: true },
      { id: 'product-2', productId: 2, name: 'Carrots', price: 3.5, quantity: 1, budget: 'go_fresh', available: true },
    ],
  }),
}));

import { AppLayout } from '../AppLayout';

describe('AppLayout', () => {
  beforeEach(() => {
    isMobile = true;
  });

  describe('on a phone', () => {
    it('shows the cart bar', () => {
      render(<AppLayout>page</AppLayout>);
      expect(screen.getByRole('region', { name: 'Cart summary' })).toBeInTheDocument();
    });

    it('shows what is left in each balance, since the sider is hidden', () => {
      render(<AppLayout>page</AppLayout>);
      const bar = screen.getByRole('region', { name: 'Cart summary' });

      // The vouchers pay for the Go Fresh carrots too: $40 - $1.50 - $3.50
      expect(within(bar).getByText('Food left: $35.00')).toBeInTheDocument();
      expect(within(bar).getByText('Hygiene left: $0.00')).toBeInTheDocument();
      expect(within(bar).getByText('Go Fresh left: $6.50')).toBeInTheDocument();
      expect(screen.queryByText('sider')).not.toBeInTheDocument();
    });

    it('opens the cart drawer from the bar', async () => {
      render(<AppLayout>page</AppLayout>);
      const bar = screen.getByRole('region', { name: 'Cart summary' });

      await userEvent.click(within(bar).getByRole('button', { name: /view cart/i }));

      expect(screen.getByText('cart drawer open')).toBeInTheDocument();
    });

    it('opens the same drawer from the header cart icon', async () => {
      render(<AppLayout>page</AppLayout>);
      await userEvent.click(screen.getByRole('button', { name: 'Open cart' }));
      expect(screen.getByText('cart drawer open')).toBeInTheDocument();
    });
  });

  describe('on desktop', () => {
    it('uses the sider instead of the cart bar', () => {
      isMobile = false;
      render(<AppLayout>page</AppLayout>);

      expect(screen.queryByRole('region', { name: 'Cart summary' })).not.toBeInTheDocument();
      expect(screen.getByText('sider')).toBeInTheDocument();
    });
  });
});
