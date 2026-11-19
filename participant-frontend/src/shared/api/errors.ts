/**
 * The message the backend sent with a failed request, for showing to the
 * participant. Server messages arrive already translated.
 */
import { isAxiosError } from 'axios';

export const serverErrorMessage = (error: unknown): string | null => {
  if (!isAxiosError(error)) return null;
  const data = error.response?.data as { error?: unknown; detail?: unknown } | undefined;
  for (const message of [data?.error, data?.detail]) {
    if (typeof message === 'string' && message.trim()) return message;
  }
  return null;
};

/** The machine-readable `code` and HTTP status of a failed request. */
export const apiErrorDetails = (
  error: unknown
): { status: number | null; code: string | null; data: Record<string, unknown> } => {
  if (!isAxiosError(error)) return { status: null, code: null, data: {} };
  const data = (error.response?.data ?? {}) as Record<string, unknown>;
  return {
    status: error.response?.status ?? null,
    code: typeof data.code === 'string' ? data.code : null,
    data,
  };
};
