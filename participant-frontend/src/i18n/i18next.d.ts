/**
 * Type-safe translation keys: t('...') autocompletes and typechecks
 * against the English catalog, which is the source of truth.
 */
import 'i18next';
import type en from '../locales/en.json';

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation';
    resources: {
      translation: typeof en;
    };
    returnNull: false;
  }
}
