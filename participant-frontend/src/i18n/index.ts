/**
 * i18next initialization for the participant app.
 *
 * Language precedence at startup: localStorage → browser language → English.
 * After login, the participant's saved backend preference wins — applied by
 * AuthContext via useLanguagePreference.
 *
 * Both locales are bundled statically (~15 KB each) so the PWA works offline
 * in either language. Revisit lazy-loading only if the language list grows.
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import en from '../locales/en.json';
import es from '../locales/es.json';
import {
  DEFAULT_LANGUAGE,
  LANGUAGE_STORAGE_KEY,
  SUPPORTED_LANGUAGE_CODES,
} from './languages';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      es: { translation: es },
    },
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: SUPPORTED_LANGUAGE_CODES,
    nonExplicitSupportedLngs: true,
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: LANGUAGE_STORAGE_KEY,
      caches: ['localStorage'],
    },
    interpolation: {
      // React already escapes rendered strings
      escapeValue: false,
    },
    returnNull: false,
  });

/**
 * Translate a key computed at runtime (backend status codes, error codes,
 * day names) that can't satisfy the compile-time key union. Falls back to
 * `defaultValue` when the key has no catalog entry.
 */
export const translateDynamic = (
  key: string,
  options?: Record<string, unknown>
): string => (i18n.t as (k: string, o?: Record<string, unknown>) => string)(key, options);

export default i18n;
