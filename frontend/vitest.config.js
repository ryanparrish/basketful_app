import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    setupFiles: ['./setupTests.js'],
    globals: true,
    environment: 'jsdom',
  },
});