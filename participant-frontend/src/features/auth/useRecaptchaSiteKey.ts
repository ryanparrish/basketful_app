/**
 * The program's reCAPTCHA v2 site key. Falls back to Google's public test
 * key (which always passes) when none is configured or the config can't load.
 */
import { useEffect, useState } from 'react';
import { getProgramConfig } from '../../shared/api/endpoints';

export const RECAPTCHA_TEST_SITE_KEY = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI';

export const useRecaptchaSiteKey = (): { siteKey: string | null; isLoading: boolean } => {
  const [siteKey, setSiteKey] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProgramConfig()
      .then((config) => {
        const configured = config?.recaptcha_site_key;
        const usable = configured && configured !== 'test-public-key';
        if (!cancelled) setSiteKey(usable ? configured : RECAPTCHA_TEST_SITE_KEY);
      })
      .catch(() => {
        if (!cancelled) setSiteKey(RECAPTCHA_TEST_SITE_KEY);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { siteKey, isLoading: siteKey === null };
};
