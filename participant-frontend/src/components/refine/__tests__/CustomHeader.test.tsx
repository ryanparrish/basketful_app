/**
 * Tests for CustomHeader — the cart button must be reachable at every
 * breakpoint, and phones (no sider) get Order History in the user menu.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

let isMobile = false;
const mockGo = vi.fn();

vi.mock('@mui/material', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@mui/material')>()),
  useMediaQuery: () => isMobile,
}));

vi.mock('@refinedev/core', () => ({
  useLogout: () => ({ mutate: vi.fn() }),
  useGetIdentity: () => ({ data: { name: 'Ryan', username: 'ryan', customer_number: 'C-1' } }),
  useGo: () => mockGo,
}));

vi.mock('../../../providers/CartProvider', () => ({
  useCartContext: () => ({ totalItems: 2 }),
}));

vi.mock('../../../shared/api/endpoints', () => ({
  getThemeConfig: vi.fn().mockResolvedValue({}),
}));

vi.mock('../../LanguageSwitcher', () => ({
  LanguageSwitcher: () => null,
}));

import { CustomHeader } from '../CustomHeader';

function renderHeader(onCartClick = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CustomHeader onCartClick={onCartClick} />
    </QueryClientProvider>
  );
  return { onCartClick };
}

describe('CustomHeader', () => {
  beforeEach(() => {
    mockGo.mockReset();
  });

  it.each([
    ['desktop', false],
    ['mobile', true],
  ])('has a cart button on %s', async (_label, mobile) => {
    isMobile = mobile;
    const { onCartClick } = renderHeader();

    await userEvent.click(screen.getByRole('button', { name: /open cart/i }));

    expect(onCartClick).toHaveBeenCalledOnce();
  });

  it('offers Order History in the user menu on mobile', async () => {
    isMobile = true;
    renderHeader();

    await userEvent.click(screen.getByText('R'));
    await userEvent.click(screen.getByRole('menuitem', { name: /order history/i }));

    expect(mockGo).toHaveBeenCalledWith({ to: '/orders' });
  });

  it('leaves Order History to the sider on desktop', async () => {
    isMobile = false;
    renderHeader();

    await userEvent.click(screen.getByText('R'));

    expect(screen.queryByRole('menuitem', { name: /order history/i })).not.toBeInTheDocument();
  });
});
