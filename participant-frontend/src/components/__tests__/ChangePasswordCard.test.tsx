/**
 * Tests for ChangePasswordCard — the Account page's voluntary password change
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChangePasswordCard } from '../ChangePasswordCard';

vi.mock('../../shared/api/endpoints', () => ({
  changePassword: vi.fn(),
}));

import { changePassword } from '../../shared/api/endpoints';
const mockChangePassword = vi.mocked(changePassword);

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ChangePasswordCard />
    </QueryClientProvider>
  );
}

async function fill(current: string, next: string, confirm: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/current password/i), current);
  await user.type(screen.getByLabelText(/^new password/i), next);
  await user.type(screen.getByLabelText(/confirm new password/i), confirm);
  await user.click(screen.getByRole('button', { name: /change password/i }));
}

describe('ChangePasswordCard', () => {
  beforeEach(() => {
    mockChangePassword.mockReset();
  });

  it('sends the current and new password, then clears the form', async () => {
    mockChangePassword.mockResolvedValue(undefined);
    renderCard();

    await fill('old-pass', 'Harvest-Basket-2026', 'Harvest-Basket-2026');

    await waitFor(() => {
      expect(screen.getByText(/your password has been changed/i)).toBeInTheDocument();
    });
    expect(mockChangePassword.mock.calls[0][0]).toEqual({
      current_password: 'old-pass',
      new_password: 'Harvest-Basket-2026',
    });
    expect(screen.getByLabelText(/current password/i)).toHaveValue('');
  });

  it("doesn't send anything when the new passwords don't match", async () => {
    renderCard();

    await fill('old-pass', 'Harvest-Basket-2026', 'Harvest-Basket-2025');

    expect(screen.getByText(/new passwords don't match/i)).toBeInTheDocument();
    expect(mockChangePassword).not.toHaveBeenCalled();
  });

  it("shows the server's reason next to the field", async () => {
    mockChangePassword.mockRejectedValue({
      response: {
        status: 400,
        data: { current_password: ['Your current password is incorrect.'] },
      },
    });
    renderCard();

    await fill('wrong', 'Harvest-Basket-2026', 'Harvest-Basket-2026');

    await waitFor(() => {
      expect(screen.getByText(/current password is incorrect/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/could not be changed/i)).not.toBeInTheDocument();
  });

  it('shows a general message for other failures', async () => {
    mockChangePassword.mockRejectedValue({ response: { status: 500 } });
    renderCard();

    await fill('old-pass', 'Harvest-Basket-2026', 'Harvest-Basket-2026');

    await waitFor(() => {
      expect(screen.getByText(/could not be changed/i)).toBeInTheDocument();
    });
  });
});
