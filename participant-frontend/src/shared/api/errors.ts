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
