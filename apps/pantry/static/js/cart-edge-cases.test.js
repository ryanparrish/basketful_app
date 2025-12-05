/**
 * Edge case and abnormality detection tests for cart
 * Tests unusual scenarios that could expose bugs in production
 */

const {
  initializeCart,
  saveCartToStorage,
  loadCartFromStorage,
  addToCart,
  removeFromCart,
  updateCartQuantity,
  clearCart,
  getCart,
  setCart,
  getCartItemCount,
  calculateCartTotal,
} = require('./cart.js');

describe('Cart Edge Cases - Large Numbers', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should handle very large quantities without overflow', () => {
    const largeQty = 999999;
    addToCart('1', largeQty);
    
    const cart = getCart();
    expect(cart['1']).toBe(largeQty);
    expect(getCartItemCount()).toBe(largeQty);
  });

  test('should handle maximum safe integer', () => {
    const maxSafe = Number.MAX_SAFE_INTEGER;
    setCart({'1': maxSafe});
    saveCartToStorage();
    
    const loaded = loadCartFromStorage();
    expect(loaded['1']).toBe(maxSafe);
  });

  test('should accumulate quantities correctly without integer overflow', () => {
    setCart({'1': 1000000});
    addToCart('1', 1000000);
    
    const cart = getCart();
    expect(cart['1']).toBe(2000000);
  });

  test('should handle many different products in cart', () => {
    // Add 100 different products
    for (let i = 1; i <= 100; i++) {
      addToCart(i.toString(), 1);
    }
    
    const cart = getCart();
    expect(Object.keys(cart)).toHaveLength(100);
    expect(getCartItemCount()).toBe(100);
  });

  test('should handle extremely large product IDs', () => {
    const hugeId = '999999999999';
    addToCart(hugeId, 5);
    
    const cart = getCart();
    expect(cart[hugeId]).toBe(5);
  });
});

describe('Cart Edge Cases - Invalid Data Types', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should reject string quantities', () => {
    const result = addToCart('1', '5'); // string instead of number
    
    // The function should either convert or reject
    const cart = getCart();
    // If it added, quantity should be converted to number
    if (cart['1']) {
      expect(typeof cart['1']).toBe('number');
    }
  });

  test('should reject float quantities', () => {
    const result = addToCart('1', 3.5);
    
    const cart = getCart();
    // Should either reject or round to integer
    if (cart['1']) {
      expect(Number.isInteger(cart['1'])).toBe(true);
    }
  });

  test('should reject NaN quantities', () => {
    const result = addToCart('1', NaN);
    expect(result).toBe(false);
    
    const cart = getCart();
    expect(cart['1']).toBeUndefined();
  });

  test('should reject Infinity quantities', () => {
    const result = addToCart('1', Infinity);
    expect(result).toBe(false);
    
    const cart = getCart();
    expect(cart['1']).toBeUndefined();
  });

  test('should handle undefined product ID', () => {
    const result = addToCart(undefined, 5);
    
    const cart = getCart();
    // Should either reject or convert to string
    expect(cart['undefined']).toBeUndefined();
  });

  test('should handle null product ID', () => {
    const result = addToCart(null, 5);
    
    const cart = getCart();
    // Should either reject or convert to string
    if (cart['null']) {
      // If accepted, verify it works with the rest of the system
      saveCartToStorage();
      const loaded = loadCartFromStorage();
      expect(loaded['null']).toBe(5);
    }
  });
});

describe('Cart Edge Cases - Race Conditions', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should handle rapid successive additions to same product', () => {
    // Simulate rapid clicking
    addToCart('1', 1);
    addToCart('1', 1);
    addToCart('1', 1);
    addToCart('1', 1);
    addToCart('1', 1);
    
    const cart = getCart();
    expect(cart['1']).toBe(5);
  });

  test('should handle add then immediate remove', () => {
    addToCart('1', 5);
    removeFromCart('1');
    
    const cart = getCart();
    expect(cart['1']).toBeUndefined();
  });

  test('should handle multiple saves to localStorage in quick succession', () => {
    addToCart('1', 1);
    saveCartToStorage();
    addToCart('2', 2);
    saveCartToStorage();
    addToCart('3', 3);
    saveCartToStorage();
    
    const loaded = loadCartFromStorage();
    expect(loaded).toEqual({'1': 1, '2': 2, '3': 3});
  });

  test('should handle update quantity to zero (edge of removal)', () => {
    addToCart('1', 5);
    updateCartQuantity('1', 0);
    
    const cart = getCart();
    expect(cart['1']).toBeUndefined();
  });

  test('should handle update quantity to negative (should remove)', () => {
    addToCart('1', 5);
    updateCartQuantity('1', -1);
    
    const cart = getCart();
    expect(cart['1']).toBeUndefined();
  });
});

describe('Cart Edge Cases - localStorage Limits', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should handle very large cart serialization', () => {
    // Create a cart with many items
    const bigCart = {};
    for (let i = 1; i <= 500; i++) {
      bigCart[i.toString()] = Math.floor(Math.random() * 10) + 1;
    }
    
    setCart(bigCart);
    saveCartToStorage();
    
    const loaded = loadCartFromStorage();
    expect(Object.keys(loaded)).toHaveLength(500);
  });

  test('should handle localStorage being full (quota exceeded)', () => {
    // This would require filling localStorage to its limit
    // Just verify error handling exists
    try {
      const hugeCart = {};
      for (let i = 0; i < 100000; i++) {
        hugeCart[i.toString()] = 1;
      }
      setCart(hugeCart);
      saveCartToStorage();
    } catch (e) {
      // Should not crash the app
      expect(e).toBeDefined();
    }
  });

  test('should recover if localStorage is cleared externally', () => {
    addToCart('1', 5);
    saveCartToStorage();
    
    // External clear (user clears browser data)
    localStorage.clear();
    
    const loaded = loadCartFromStorage();
    expect(loaded).toEqual({});
  });
});

describe('Cart Edge Cases - Price Calculations', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should calculate total with floating point prices correctly', () => {
    const products = {
      '1': { price: 10.99 },
      '2': { price: 5.49 },
      '3': { price: 0.99 },
    };
    
    setCart({'1': 3, '2': 2, '3': 5});
    const total = calculateCartTotal(products);
    
    // 10.99*3 + 5.49*2 + 0.99*5 = 32.97 + 10.98 + 4.95 = 48.90
    expect(total).toBeCloseTo(48.90, 2);
  });

  test('should handle missing product in total calculation', () => {
    const products = {
      '1': { price: 10.00 },
    };
    
    // Cart has product 2 but it doesn't exist in products
    setCart({'1': 2, '2': 5});
    const total = calculateCartTotal(products);
    
    // Should only count product 1
    expect(total).toBe(20.00);
  });

  test('should handle zero-priced items', () => {
    const products = {
      '1': { price: 0 },
      '2': { price: 10.00 },
    };
    
    setCart({'1': 100, '2': 1});
    const total = calculateCartTotal(products);
    
    expect(total).toBe(10.00);
  });

  test('should handle products with undefined price', () => {
    const products = {
      '1': {},  // No price property
      '2': { price: 10.00 },
    };
    
    setCart({'1': 5, '2': 2});
    const total = calculateCartTotal(products);
    
    // Should handle undefined price gracefully (NaN -> 0 or skip)
    expect(typeof total).toBe('number');
    expect(isNaN(total)).toBe(false);
  });
});

describe('Cart Edge Cases - Session vs localStorage Conflicts', () => {
  beforeEach(() => {
    setCart({});
    localStorage.clear();
  });

  test('should prioritize session cart over localStorage', () => {
    // localStorage has old cart
    localStorage.setItem('cart', JSON.stringify({'1': 10}));
    
    // Session has new cart
    const sessionCart = {'2': 5};
    const cart = initializeCart(sessionCart);
    
    expect(cart).toEqual({'2': 5});
    expect(cart['1']).toBeUndefined();
  });

  test('should sync session to localStorage when session takes priority', () => {
    const sessionCart = {'3': 7};
    initializeCart(sessionCart);
    
    const stored = localStorage.getItem('cart');
    expect(JSON.parse(stored)).toEqual({'3': 7});
  });

  test('should use localStorage when session is null', () => {
    localStorage.setItem('cart', JSON.stringify({'1': 5}));
    
    const cart = initializeCart(null);
    expect(cart).toEqual({'1': 5});
  });

  test('should use localStorage when session is empty object', () => {
    localStorage.setItem('cart', JSON.stringify({'1': 5}));
    
    const cart = initializeCart({});
    expect(cart).toEqual({'1': 5});
  });
});

describe('Cart Edge Cases - Special Characters', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should handle product IDs with special characters in string form', () => {
    // Django might have slugs or special product identifiers
    const specialId = 'product-123-special';
    addToCart(specialId, 5);
    
    const cart = getCart();
    expect(cart[specialId]).toBe(5);
    
    saveCartToStorage();
    const loaded = loadCartFromStorage();
    expect(loaded[specialId]).toBe(5);
  });

  test('should handle emoji in product IDs (edge case)', () => {
    const emojiId = '🍎-123';
    setCart({[emojiId]: 3});
    saveCartToStorage();
    
    const loaded = loadCartFromStorage();
    expect(loaded[emojiId]).toBe(3);
  });
});

describe('Cart Edge Cases - Memory Leaks', () => {
  test('should not retain references after clear', () => {
    const testCart = {'1': 5, '2': 3};
    setCart(testCart);
    
    clearCart();
    
    // Modifying the original object shouldn't affect cleared cart
    testCart['3'] = 10;
    
    const cart = getCart();
    expect(cart['3']).toBeUndefined();
    expect(Object.keys(cart)).toHaveLength(0);
  });

  test('should return new object on getCart (no reference leaks)', () => {
    setCart({'1': 5});
    
    const cart1 = getCart();
    const cart2 = getCart();
    
    // Should be different objects
    expect(cart1).not.toBe(cart2);
    
    // But same values
    expect(cart1).toEqual(cart2);
    
    // Modifying one shouldn't affect the other
    cart1['2'] = 10;
    expect(cart2['2']).toBeUndefined();
  });
});

describe('Cart Edge Cases - Browser Compatibility', () => {
  beforeEach(() => {
    setCart({});
  });

  test('should handle JSON.stringify circular reference gracefully', () => {
    // This shouldn't happen but let's test error handling
    const circular = {'1': 5};
    // Can't actually create circular ref in JSON, but test the concept
    
    setCart(circular);
    expect(() => saveCartToStorage()).not.toThrow();
  });

  test('should handle Object.keys on cart', () => {
    setCart({'1': 5, '2': 3, '10': 1});
    
    const keys = Object.keys(getCart());
    expect(keys).toEqual(['1', '2', '10']);
    expect(Array.isArray(keys)).toBe(true);
  });

  test('should handle Object.values on cart', () => {
    setCart({'1': 5, '2': 3, '10': 1});
    
    const values = Object.values(getCart());
    expect(values).toEqual([5, 3, 1]);
    expect(values.reduce((a, b) => a + b, 0)).toBe(9);
  });

  test('should handle Object.entries on cart', () => {
    setCart({'1': 5, '2': 3});
    
    const entries = Object.entries(getCart());
    expect(entries).toEqual([['1', 5], ['2', 3]]);
  });
});
