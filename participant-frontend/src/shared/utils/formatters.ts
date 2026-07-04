/**
 * Locale-aware formatting helpers.
 *
 * Prices are always US dollars — only the display formatting follows the
 * user's language. Prefer the useFormatters hook in components so output
 * re-renders when the language changes.
 */

export const formatCurrency = (amount: number | string, locale: string): string =>
  new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'USD',
  }).format(Number(amount) || 0);

export const formatDate = (date: Date, locale: string): string =>
  new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);

export const formatTime = (date: Date, locale: string): string =>
  new Intl.DateTimeFormat(locale, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);

/** Format a backend "HH:MM" or "HH:MM:SS" time-of-day string. */
export const formatTimeOfDay = (timeString: string, locale: string): string => {
  const [hours, minutes] = timeString.split(':').map(Number);
  const date = new Date();
  date.setHours(hours, minutes, 0, 0);
  return formatTime(date, locale);
};
