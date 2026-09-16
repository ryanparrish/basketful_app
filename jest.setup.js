// Add custom jest matchers from jest-dom
require('@testing-library/jest-dom');

// Create storage mock class that maintains state
class StorageMock {
  constructor() {
    this.store = {};
  }

  getItem(key) {
    return key in this.store ? this.store[key] : null;
  }

  setItem(key, value) {
    this.store[key] = value.toString();
  }

  removeItem(key) {
    delete this.store[key];
  }

  clear() {
    this.store = {};
  }

  get length() {
    return Object.keys(this.store).length;
  }

  key(index) {
    const keys = Object.keys(this.store);
    return keys[index] || null;
  }
}

// Set up storage mocks
global.localStorage = new StorageMock();
global.sessionStorage = new StorageMock();

// cart.js syncs to /update-cart/ via fetch on every save; jsdom doesn't
// implement fetch, so without this every cart-mutating test throws
// "fetch is not defined" before it can assert anything.
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ status: 'ok', balances: {} }),
  })
);

// Reset storage state before each test
beforeEach(() => {
  // Clear storage data
  global.localStorage.store = {};
  global.sessionStorage.store = {};
  global.fetch.mockClear();
});
