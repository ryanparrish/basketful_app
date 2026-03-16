/**
 * Centralized API URL utilities.
 *
 * VITE_API_URL may accidentally include a trailing "/api/v1" suffix (e.g. in
 * environments where the env var was set to the full API base path rather than
 * the bare origin).  We normalise it here once so every consumer gets a
 * consistent value and the path is never doubled.
 */

/** Bare origin — e.g. "https://example.com" or "http://localhost:8000" */
export const API_ORIGIN = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/\/api\/v1\/?$/, '')
  .replace(/\/$/, '');

/** Fully-qualified API base — e.g. "https://example.com/api/v1"
 *  Use this when the consumer does NOT append "/api/v1" itself (e.g. dataProvider). */
export const API_BASE = `${API_ORIGIN}/api/v1`;

/** Bare origin alias — use when fetch calls already append "/api/v1/..." */
export const API_URL = API_ORIGIN;
