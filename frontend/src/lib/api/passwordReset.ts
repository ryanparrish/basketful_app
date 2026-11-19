/**
 * Password reset API (#137). Anonymous endpoints; every error is a 400 with
 * a machine-readable `code` (429 when rate limited).
 */
import { isAxiosError } from 'axios';
import apiClient from './apiClient';

export interface PasswordResetLink {
  uid: string;
  token: string;
}

export interface PasswordResetResult {
  app: 'participant' | 'staff';
  /** What the account signs in with: username for staff. */
  sign_in_as: string;
}

export const requestPasswordReset = async (identifier: string, recaptchaToken: string) => {
  await apiClient.post('/auth/password-reset/', { identifier, recaptcha_token: recaptchaToken });
};

export const validatePasswordResetLink = async (link: PasswordResetLink) => {
  await apiClient.post('/auth/password-reset/validate/', link);
};

export const confirmPasswordReset = async (
  link: PasswordResetLink,
  newPassword: string
): Promise<PasswordResetResult> => {
  const response = await apiClient.post<PasswordResetResult>('/auth/password-reset/confirm/', {
    ...link,
    new_password: newPassword,
  });
  return response.data;
};

/** HTTP status, `code` and body of a failed request. */
export const apiErrorDetails = (error: unknown) => {
  if (!isAxiosError(error)) return { status: null, code: null, data: {} as Record<string, unknown> };
  const data = (error.response?.data ?? {}) as Record<string, unknown>;
  return {
    status: error.response?.status ?? null,
    code: typeof data.code === 'string' ? data.code : null,
    data,
  };
};
