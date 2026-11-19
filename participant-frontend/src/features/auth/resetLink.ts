/**
 * Holds the emailed reset link's uid and token for this tab, so the token
 * can come off the address bar (where history, screenshots and Referer
 * headers would carry it) without being lost on a reload.
 */
import type { PasswordResetLink } from '../../shared/api/endpoints';

const STORAGE_KEY = 'basketful_reset_link';

export const storeResetLink = (link: PasswordResetLink): void => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(link));
  } catch {
    // Private mode without storage: the page will ask for a new link
  }
};

export const readResetLink = (): PasswordResetLink | null => {
  try {
    const stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? 'null');
    return stored?.uid && stored?.token ? stored : null;
  } catch {
    return null;
  }
};

export const clearResetLink = (): void => {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing stored
  }
};
