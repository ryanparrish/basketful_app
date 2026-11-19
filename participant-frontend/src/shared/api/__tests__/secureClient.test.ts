/**
 * #135: a 401 from an endpoint that does not depend on a session (sign-in,
 * password reset) must not be reported as an expired session. Only a failed
 * token refresh is a real expiry.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios, { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';
import { apiClient, SESSION_EXPIRED_EVENT } from '../secureClient';

const reject401 = (config: InternalAxiosRequestConfig, data: unknown = {}) =>
  Promise.reject(
    new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, null, {
      status: 401,
      statusText: 'Unauthorized',
      headers: {},
      config,
      data,
    })
  );

const always401: AxiosAdapter = (config) =>
  reject401(config, { detail: 'Incorrect password.', code: 'invalid_password' });

let sessionExpired: ReturnType<typeof vi.fn<(event: Event) => void>>;
const originalAdapter = apiClient.defaults.adapter;

beforeEach(() => {
  sessionExpired = vi.fn<(event: Event) => void>();
  window.addEventListener(SESSION_EXPIRED_EVENT, sessionExpired);
  apiClient.defaults.adapter = always401;
});

afterEach(() => {
  window.removeEventListener(SESSION_EXPIRED_EVENT, sessionExpired);
  apiClient.defaults.adapter = originalAdapter;
  vi.restoreAllMocks();
});

describe('secureClient 401 handling', () => {
  it('rejects a failed sign-in without reporting an expired session', async () => {
    await expect(
      apiClient.post('/auth/login/', { username: 'someone', password: 'wrong' })
    ).rejects.toMatchObject({ response: { status: 401, data: { code: 'invalid_password' } } });

    expect(sessionExpired).not.toHaveBeenCalled();
  });

  it.each([
    '/auth/password-reset/',
    '/auth/password-reset/validate/',
    '/auth/password-reset/confirm/',
  ])('rejects a 401 from %s without reporting an expired session', async (url) => {
    await expect(apiClient.post(url, {})).rejects.toMatchObject({ response: { status: 401 } });

    expect(sessionExpired).not.toHaveBeenCalled();
  });

  it('reports an expired session when the refresh endpoint itself returns 401', async () => {
    await expect(apiClient.post('/auth/refresh/', {})).rejects.toMatchObject({
      response: { status: 401 },
    });

    expect(sessionExpired).toHaveBeenCalledTimes(1);
  });

  it('reports an expired session when a data request 401s and the refresh token has expired', async () => {
    vi.spyOn(axios, 'post').mockImplementation((url) =>
      reject401({ url, headers: {} } as InternalAxiosRequestConfig, { code: 'token_expired' })
    );

    await expect(apiClient.get('/orders/')).rejects.toMatchObject({ response: { status: 401 } });

    expect(sessionExpired).toHaveBeenCalledTimes(1);
  });
});
