/**
 * Staff password reset pages (#137).
 */
import { forwardRef } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import ForgotPasswordPage from './ForgotPassword';
import ResetPasswordPage from './ResetPassword';

vi.mock('../lib/api/passwordReset', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/api/passwordReset')>()),
  requestPasswordReset: vi.fn(),
  validatePasswordResetLink: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));
vi.mock('../lib/useRecaptchaSiteKey', () => ({
  useRecaptchaSiteKey: () => ({ siteKey: 'site-key', isLoading: false }),
}));
vi.mock('react-google-recaptcha', () => ({
  default: forwardRef(({ onChange }: { onChange: (token: string) => void }, _ref) => (
    <button type="button" onClick={() => onChange('recaptcha-token')}>solve recaptcha</button>
  )),
}));

import {
  confirmPasswordReset,
  requestPasswordReset,
  validatePasswordResetLink,
} from '../lib/api/passwordReset';

const SignInProbe = () => {
  const state = useLocation().state as { passwordSet?: boolean; username?: string } | null;
  return <div>sign in {state?.passwordSet ? 'after reset' : ''} as {state?.username}</div>;
};

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<SignInProbe />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  vi.mocked(requestPasswordReset).mockReset();
  vi.mocked(validatePasswordResetLink).mockReset();
  vi.mocked(confirmPasswordReset).mockReset();
  sessionStorage.clear();
});

describe('Staff ForgotPasswordPage', () => {
  it('sends the username with the reCAPTCHA token', async () => {
    vi.mocked(requestPasswordReset).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderAt('/forgot-password');

    await user.type(screen.getByLabelText(/username or email/i), 'coordinator');
    await user.click(screen.getByRole('button', { name: /solve recaptcha/i }));
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(await screen.findByText(/if an account matches/i)).toBeInTheDocument();
    expect(requestPasswordReset).toHaveBeenCalledWith('coordinator', 'recaptcha-token');
  });
});

describe('Staff ResetPasswordPage', () => {
  it('sets the password and returns to sign-in with the username', async () => {
    vi.mocked(validatePasswordResetLink).mockResolvedValue(undefined);
    vi.mocked(confirmPasswordReset).mockResolvedValue({ app: 'staff', sign_in_as: 'coordinator' });
    const user = userEvent.setup();
    renderAt('/reset-password/MTI/abc-123');

    await user.type(await screen.findByLabelText(/^new password/i), 'Harvest-Basket-2026');
    await user.type(screen.getByLabelText(/confirm new password/i), 'Harvest-Basket-2026');
    await user.click(screen.getByRole('button', { name: /set password/i }));

    expect(await screen.findByText(/sign in after reset as coordinator/i)).toBeInTheDocument();
    expect(confirmPasswordReset).toHaveBeenCalledWith({ uid: 'MTI', token: 'abc-123' }, 'Harvest-Basket-2026');
  });

  it('offers a new link when the link has expired', async () => {
    vi.mocked(validatePasswordResetLink).mockRejectedValue(new Error('invalid'));
    renderAt('/reset-password/MTI/old-token');

    expect(await screen.findByText(/no longer valid/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /get a new link/i })).toHaveAttribute('href', '/forgot-password');
  });
});
