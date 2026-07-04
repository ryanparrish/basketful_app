import '@testing-library/jest-dom';
import { beforeAll } from 'vitest';

// Initialize i18n for component tests — pinned to English so existing
// English-text assertions keep passing regardless of the machine's locale.
import i18n from '../i18n';

beforeAll(async () => {
  await i18n.changeLanguage('en');
});
