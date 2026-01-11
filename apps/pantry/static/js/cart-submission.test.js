/**
 * Tests for cart submission and clearing behavior
 * Validates that cart data matches what's sent to server
 * and that cart is properly cleared after order submission
 */

const {
  initializeCart,
  saveCartToStorage,
  loadCartFromStorage,
  addToCart,
  clearCart,
  getCart,
  setCart,
  getCartItemCount,
} = require('./cart.js');

describe('Cart Submission Validation', () => {
  beforeEach(() => {
    // Reset cart state
    setCart({});
  });

  test('should preserve exact cart structure when saving to localStorage', () => {
    const testCart = {
      '1': 5,
      '2': 3,
      '10': 1,
    };
    
    setCart(testCart);
    saveCartToStorage();
    
    const loaded = loadCartFromStorage();
    expect(loaded).toEqual(testCart);
    expect(Object.keys(loaded)).toEqual(['1', '2', '10']);
  });

  test('should maintain product IDs as strings (matching server expectation)', () => {
    addToCart('123', 5);
    addToCart('456', 2);
    
    const cart = getCart();
    
    // Cart keys should be strings (as Django expects)
    expect(Object.keys(cart)).toEqual(['123', '456']);
    expect(typeof Object.keys(cart)[0]).toBe('string');
  });

  test('should serialize cart to JSON matching server format', () => {
    const testCart = {
      '1': 3,
      '5': 2,
      '7': 1,
    };
    
    setCart(testCart);
    saveCartToStorage();
    
    const stored = localStorage.getItem('cart');
    const parsed = JSON.parse(stored);
    
    // Should be valid JSON
    expect(parsed).toEqual(testCart);
    
    // Should match Django's expected format: {"product_id": quantity}
    expect(parsed['1']).toBe(3);
    expect(parsed['5']).toBe(2);
    expect(parsed['7']).toBe(1);
  });

  test('should handle empty cart submission gracefully', () => {
    clearCart();
    
    const cart = getCart();
    expect(Object.keys(cart)).toHaveLength(0);
    
    // Empty cart should serialize to empty object
    const stored = localStorage.getItem('cart');
    expect(JSON.parse(stored)).toEqual({});
  });

  test('should preserve cart quantities accurately', () => {
    addToCart('1', 10);
    addToCart('2', 5);
    addToCart('1', 3); // Add more to existing item
    
    const cart = getCart();
    
    expect(cart['1']).toBe(13); // 10 + 3
    expect(cart['2']).toBe(5);
  });

  test('should validate cart has no undefined or null quantities', () => {
    const testCart = {
      '1': 5,
      '2': 3,
      '3': 7,
    };
    
    setCart(testCart);
    const cart = getCart();
    
    // All quantities should be numbers > 0
    Object.values(cart).forEach(qty => {
      expect(typeof qty).toBe('number');
      expect(qty).toBeGreaterThan(0);
      expect(Number.isInteger(qty)).toBe(true);
    });
  });
});

describe('Cart Clearing and Session Management', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should completely clear cart from memory', () => {
    addToCart('1', 5);
    addToCart('2', 3);
    expect(getCartItemCount()).toBe(8);
    
    clearCart();
    
    const cart = getCart();
    expect(Object.keys(cart)).toHaveLength(0);
    expect(getCartItemCount()).toBe(0);
  });

  test('should clear cart from localStorage', () => {
    addToCart('1', 5);
    addToCart('2', 3);
    saveCartToStorage();
    
    clearCart();
    
    const stored = localStorage.getItem('cart');
    const parsed = JSON.parse(stored);
    expect(parsed).toEqual({});
  });

  test('should not retain cart data between sessions', () => {
    // Simulate order submission
    addToCart('1', 5);
    addToCart('2', 3);
    saveCartToStorage();
    
    // Simulate order success - clear cart
    clearCart();
    
    // Simulate new session - load cart
    const newCart = loadCartFromStorage();
    expect(Object.keys(newCart)).toHaveLength(0);
    expect(getCartItemCount()).toBe(0);
  });

  test('should handle localStorage.removeItem for complete cleanup', () => {
    addToCart('1', 5);
    saveCartToStorage();
    
    // Simulate what order_success.html does
    localStorage.removeItem('cart');
    
    const loaded = loadCartFromStorage();
    expect(loaded).toEqual({});
  });

  test('should not have stale data after clearing', () => {
    // First order
    addToCart('1', 5);
    addToCart('2', 3);
    saveCartToStorage();
    
    const firstOrder = getCart();
    expect(firstOrder).toEqual({'1': 5, '2': 3});
    
    // Clear after submission
    clearCart();
    localStorage.removeItem('cart');
    
    // Second order - should start fresh
    setCart({}); // Reset
    addToCart('3', 2);
    
    const secondOrder = getCart();
    expect(secondOrder).toEqual({'3': 2});
    expect(secondOrder['1']).toBeUndefined();
    expect(secondOrder['2']).toBeUndefined();
  });

  test('should initialize empty cart when localStorage is cleared', () => {
    localStorage.removeItem('cart');
    
    const cart = initializeCart({});
    expect(cart).toEqual({});
    expect(Object.keys(cart)).toHaveLength(0);
  });
});

describe('Cart Data Integrity', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should not allow negative quantities', () => {
    // addToCart should reject negative quantities
    const result = addToCart('1', -5);
    expect(result).toBe(false);
    
    const cart = getCart();
    expect(cart['1']).toBeUndefined();
  });

  test('should not allow zero quantities', () => {
    const result = addToCart('1', 0);
    expect(result).toBe(false);
    
    const cart = getCart();
    expect(cart['1']).toBeUndefined();
  });

  test('should handle concurrent cart operations', () => {
    // Simulate rapid cart updates
    addToCart('1', 1);
    addToCart('1', 2);
    addToCart('1', 3);
    
    const cart = getCart();
    expect(cart['1']).toBe(6); // Should accumulate correctly
  });

  test('should recover from corrupted localStorage data', () => {
    // Corrupt the localStorage data
    localStorage.setItem('cart', 'invalid json {{{');
    
    const cart = loadCartFromStorage();
    expect(cart).toEqual({}); // Should return empty cart on error
  });

  test('should maintain cart integrity across save/load cycles', () => {
    const originalCart = {
      '1': 5,
      '2': 3,
      '10': 15,
      '25': 1,
    };
    
    setCart(originalCart);
    saveCartToStorage();
    
    // Simulate page reload
    const loaded1 = loadCartFromStorage();
    expect(loaded1).toEqual(originalCart);
    
    // Another save/load cycle
    saveCartToStorage(loaded1);
    const loaded2 = loadCartFromStorage();
    expect(loaded2).toEqual(originalCart);
  });
});
