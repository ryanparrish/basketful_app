/**
 * Tests for the in-app password reset (#137): asking for a link, landing
 * from the email, setting the password, and coming back to sign-in.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { AxiosError, AxiosHeaders } from 'axios';
import i18n from '../../../i18n';
import { ForgotPasswordPage } from '../ForgotPasswordPage';
import { ResetLinkLanding, ResetPasswordPage } from '../ResetPasswordPage';

vi.mock('../../../shared/api/endpoints', () => ({
  getProgramConfig: vi.fn().mockResolvedValue({}),
  requestPasswordReset: vi.fn(),
  validatePasswordResetLink: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));
vi.mock('../../../shared/theme/dynamicTheme', () => ({
  useThemeConfig: () => ({ themeConfig: { app_name: 'Basketful' } }),
}));
vi.mock('../../../components/LanguageSwitcher', () => ({
  LanguageSwitcher: () => null,
}));
// A stand-in widget: one click "solves" the reCAPTCHA
vi.mock('react-google-recaptcha', () => ({
  default: React.forwardRef(({ onChange }: { onChange: (token: string) => void }, _ref) => (
    <button type="button" onClick={() => onChange('recaptcha-token')}>
      solve recaptcha
    </button>
  )),
}));

import {
  confirmPasswordReset,
  requestPasswordReset,
  validatePasswordResetLink,
} from '../../../shared/api/endpoints';

const apiError = (status: number, data: Record<string, unknown>) =>
  new AxiosError('failed', String(status), undefined, undefined, {
    status,
    data,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
  });

const SignInProbe: React.FC = () => {
  const location = useLocation();
  const state = location.state as { signInAs?: string } | null;
  return <div>sign in page{location.search} as {state?.signInAs}</div>;
};

function renderAt(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<SignInProbe />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset/:uid/:token" element={<ResetLinkLanding />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(async () => {
  vi.mocked(requestPasswordReset).mockReset();
  vi.mocked(validatePasswordResetLink).mockReset();
  vi.mocked(confirmPasswordReset).mockReset();
  sessionStorage.clear();
  await i18n.changeLanguage('en');
});

describe('ForgotPasswordPage', () => {
  async function ask(identifier: string) {
    const user = userEvent.setup();
    renderAt('/forgot-password');
    await user.type(screen.getByLabelText(/customer number or email/i), identifier);
    await user.click(await screen.findByRole('button', { name: /solve recaptcha/i }));
    await user.click(screen.getByRole('button', { name: /send reset link/i }));
  }

  it('sends the identifier with the reCAPTCHA token, then says to check email', async () => {
    vi.mocked(requestPasswordReset).mockResolvedValue(undefined);

    await ask('  C-BKM-7 ');

    expect(await screen.findByText(/check your email/i)).toBeInTheDocument();
    expect(vi.mocked(requestPasswordReset).mock.calls[0][0]).toEqual({
      identifier: 'C-BKM-7',
      recaptcha_token: 'recaptcha-token',
    });
  });

  it('explains a rate limit', async () => {
    vi.mocked(requestPasswordReset).mockRejectedValue(apiError(429, {}));

    await ask('C-BKM-7');

    expect(await screen.findByText(/too many requests/i)).toBeInTheDocument();
  });

  it('asks for an identifier before sending', async () => {
    const user = userEvent.setup();
    renderAt('/forgot-password');

    await user.click(await screen.findByRole('button', { name: /solve recaptcha/i }));
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(screen.getByText(/please enter your customer number or email/i)).toBeInTheDocument();
    expect(requestPasswordReset).not.toHaveBeenCalled();
  });

  it('links back to sign in', async () => {
    renderAt('/forgot-password');

    expect(screen.getByRole('link', { name: /back to sign in/i })).toHaveAttribute('href', '/login');
  });
});

describe('Reset link and new password', () => {
  it('takes the token off the address, sets the password and returns to sign-in', async () => {
    vi.mocked(validatePasswordResetLink).mockResolvedValue({ valid: true });
    vi.mocked(confirmPasswordReset).mockResolvedValue({ app: 'participant', sign_in_as: 'C-BKM-7' });
    const user = userEvent.setup();
    renderAt('/reset/MTI/abc-123');

    await user.type(await screen.findByLabelText(/^new password/i), 'Harvest-Basket-2026');
    await user.type(screen.getByLabelText(/confirm new password/i), 'Harvest-Basket-2026');
    await user.click(screen.getByRole('button', { name: /set password/i }));

    expect(await screen.findByText(/sign in page\?reset=success as C-BKM-7/)).toBeInTheDocument();
    expect(vi.mocked(validatePasswordResetLink).mock.calls[0][0]).toEqual({ uid: 'MTI', token: 'abc-123' });
    expect(vi.mocked(confirmPasswordReset).mock.calls[0][0]).toEqual({
      uid: 'MTI',
      token: 'abc-123',
      new_password: 'Harvest-Basket-2026',
    });
    expect(sessionStorage.length).toBe(0);
  });

  it('opens in the language the email link carries', async () => {
    vi.mocked(validatePasswordResetLink).mockResolvedValue({ valid: true });
    renderAt('/reset/MTI/abc-123?lang=es');

    expect(await screen.findByLabelText(/^nueva contraseña/i)).toBeInTheDocument();
  });

  it('offers a new link when the link has expired', async () => {
    vi.mocked(validatePasswordResetLink).mockRejectedValue(apiError(400, { code: 'invalid_link' }));
    renderAt('/reset/MTI/old-token');

    expect(await screen.findByText(/this link has expired/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /get a new link/i })).toHaveAttribute('href', '/forgot-password');
  });

  it('treats a visit without a link as expired', async () => {
    renderAt('/reset-password');

    expect(await screen.findByText(/this link has expired/i)).toBeInTheDocument();
    expect(validatePasswordResetLink).not.toHaveBeenCalled();
  });

  it("doesn't send passwords that don't match", async () => {
    vi.mocked(validatePasswordResetLink).mockResolvedValue({ valid: true });
    const user = userEvent.setup();
    renderAt('/reset/MTI/abc-123');

    await user.type(await screen.findByLabelText(/^new password/i), 'Harvest-Basket-2026');
    await user.type(screen.getByLabelText(/confirm new password/i), 'Harvest-Basket-2025');
    await user.click(screen.getByRole('button', { name: /set password/i }));

    expect(screen.getByText(/the passwords don't match/i)).toBeInTheDocument();
    expect(confirmPasswordReset).not.toHaveBeenCalled();
  });

  it("shows the server's reasons for a weak password", async () => {
    vi.mocked(validatePasswordResetLink).mockResolvedValue({ valid: true });
    vi.mocked(confirmPasswordReset).mockRejectedValue(apiError(400, {
      code: 'invalid_password',
      new_password: ['This password is too short.'],
    }));
    const user = userEvent.setup();
    renderAt('/reset/MTI/abc-123');

    await user.type(await screen.findByLabelText(/^new password/i), 'short');
    await user.type(screen.getByLabelText(/confirm new password/i), 'short');
    await user.click(screen.getByRole('button', { name: /set password/i }));

    await waitFor(() => {
      expect(screen.getByText('This password is too short.')).toBeInTheDocument();
    });
  });
});
