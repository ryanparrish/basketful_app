/**
 * Refine i18n provider — a thin adapter over the app's i18next instance
 * so Refine-rendered chrome (resource labels, error pages) localizes
 * with the rest of the app.
 */
import type { I18nProvider } from '@refinedev/core';
import i18n from '../../i18n';

export const i18nProvider: I18nProvider = {
  translate: (key, options, defaultMessage) =>
    i18n.t(key as never, { defaultValue: defaultMessage, ...(options as object) }) as string,
  changeLocale: (lang) => i18n.changeLanguage(lang),
  getLocale: () => i18n.language,
};
