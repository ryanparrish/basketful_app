import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    setupFiles: ['./setupTests.js'],
    globals: true,
    environment: 'jsdom',
    // Playwright specs live in e2e/ and run via `npm run e2e`, not vitest.
    exclude: ['node_modules/**', 'dist/**', 'e2e/**'],
  },
});