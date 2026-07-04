/**
 * Formatting helpers bound to the active language.
 */
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { formatCurrency, formatDate, formatTime, formatTimeOfDay } from '../utils/formatters';

export const useFormatters = () => {
  const { i18n } = useTranslation();
  const locale = i18n.language;

  return useMemo(
    () => ({
      formatCurrency: (amount: number | string) => formatCurrency(amount, locale),
      formatDate: (date: Date) => formatDate(date, locale),
      formatTime: (date: Date) => formatTime(date, locale),
      formatTimeOfDay: (timeString: string) => formatTimeOfDay(timeString, locale),
    }),
    [locale]
  );
};
