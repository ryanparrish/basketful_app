// Vitest setup file

// jest-dom matchers (toBeInTheDocument, ...) for vitest's expect
import '@testing-library/jest-dom/vitest';

import * as jestMock from 'jest-mock';

// Mock global objects and functions
global.jest = jestMock;

// Mock localStorage
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: jest.fn(() => null),
    setItem: jest.fn(() => null),
    removeItem: jest.fn(() => null),
    clear: jest.fn(() => null),
  },
  writable: true,
});
