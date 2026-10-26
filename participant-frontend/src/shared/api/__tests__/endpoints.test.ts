/**
 * BEH-069 (part 2) — getOrders always sends ?me=true
 *
 * This test lives in its own file because it must NOT mock the endpoints module
 * (unlike OrderHistory.test.tsx which mocks it at component level).
 * It spies on the underlying axios instance to assert the real HTTP params.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { apiClient } from '../../../shared/api/secureClient';
import { getOrders, getProgramConfig } from '../../../shared/api/endpoints';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('getOrders — BEH-069 scope enforcement', () => {
  it('always sends me=true so the backend scopes results to the authenticated user', async () => {
    // Arrange — spy on the axios instance get method
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: { results: [], count: 0 },
    });

    // Act
    await getOrders();

    // Assert — me=true must be present in the params
    expect(getSpy).toHaveBeenCalledWith(
      '/orders/',
      expect.objectContaining({
        params: expect.objectContaining({ me: 'true' }),
      })
    );
  });
});

describe('getProgramConfig', () => {
  it('reads the singleton settings object, not the list endpoint', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: { grace_enabled: true, rules_version: 'abc123' },
    });

    const config = await getProgramConfig();

    expect(getSpy).toHaveBeenCalledWith('/settings/program-config/current/');
    expect(config.rules_version).toBe('abc123');
  });
});
