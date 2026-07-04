/**
 * Single source of truth for the languages the participant app offers.
 *
 * Adding a language: add an entry here, create src/locales/<code>.json,
 * register it in src/i18n/index.ts, and add the code to the backend
 * Participant.LANGUAGE_CHOICES.
 */
export interface SupportedLanguage {
  code: string;
  /** Name shown in the switcher — always in its own language. */
  nativeName: string;
}

export const SUPPORTED_LANGUAGES: SupportedLanguage[] = [
  { code: 'en', nativeName: 'English' },
  { code: 'es', nativeName: 'Español' },
];

export const SUPPORTED_LANGUAGE_CODES = SUPPORTED_LANGUAGES.map((language) => language.code);

export const DEFAULT_LANGUAGE = 'en';

/** localStorage key persisting the anonymous/session language choice. */
export const LANGUAGE_STORAGE_KEY = 'basketful_language';
