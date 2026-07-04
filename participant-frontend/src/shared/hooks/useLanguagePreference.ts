/**
 * The single mutation point for the app language.
 *
 * Changing language:
 * 1. switches the i18next UI language (persisted to localStorage by the
 *    detector),
 * 2. persists to the participant's backend preferred_language when
 *    authenticated — so emails and future sessions match, and
 * 3. invalidates every cached query — refetches carry the new
 *    Accept-Language header, so server-translated content (product names,
 *    validation messages) comes back in the new language.
 */
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../../providers/AuthContext';
import { updateMyPreferredLanguage } from '../api/endpoints';

export const useLanguagePreference = () => {
  const { i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();

  const changeLanguage = useCallback(
    async (languageCode: string) => {
      if (languageCode === i18n.language) return;

      await i18n.changeLanguage(languageCode);

      if (isAuthenticated) {
        try {
          await updateMyPreferredLanguage(languageCode);
        } catch (error) {
          // The UI language still changed; the saved preference just didn't
          // stick. Don't block the switch over it.
          console.error('Failed to save language preference:', error);
        }
      }

      await queryClient.invalidateQueries();
    },
    [i18n, isAuthenticated, queryClient]
  );

  return {
    currentLanguage: i18n.language,
    changeLanguage,
  };
};
