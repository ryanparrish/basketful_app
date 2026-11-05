import { describe, it, expect } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { serverErrorMessage } from '../errors';

const axiosErrorWith = (data: unknown) =>
  new AxiosError('Request failed with status code 400', 'ERR_BAD_REQUEST', undefined, undefined, {
    data,
    status: 400,
    statusText: 'Bad Request',
    headers: {},
    config: { headers: new AxiosHeaders() },
  });

describe('serverErrorMessage', () => {
  it("returns the backend's error message, not axios's status text", () => {
    expect(serverErrorMessage(axiosErrorWith({ error: 'Food balance exceeded by $0.50' })))
      .toBe('Food balance exceeded by $0.50');
  });

  it('falls back to DRF detail messages, such as throttling', () => {
    expect(serverErrorMessage(axiosErrorWith({ detail: 'Request was throttled.' })))
      .toBe('Request was throttled.');
  });

  it('returns null when the server sent no message', () => {
    expect(serverErrorMessage(axiosErrorWith({}))).toBeNull();
    expect(serverErrorMessage(axiosErrorWith({ error: '  ' }))).toBeNull();
    expect(serverErrorMessage(new Error('Network Error'))).toBeNull();
  });
});
