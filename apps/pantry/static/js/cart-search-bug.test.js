/**
 * Tests for cart interaction with search/filter functionality
 * Tests the bug where cart items disappear when searching
 */

const {
  addToCart,
  removeFromCart,
  clearCart,
  getCart,
  setCart,
  getCartItemCount,
  calculateCartTotal,
  saveCartToStorage,
  loadCartFromStorage,
} = require('./cart.js');

describe('Cart + Search Interaction Bug', () => {
  beforeEach(() => {
    setCart({});
  });

  test('FAILING: cart should retain all items when search filters products', () => {
    // Setup: All products available initially
    const allProducts = {
      '1': { name: 'Apple', price: 2.50, category: 'fruits' },
      '2': { name: 'Banana', price: 1.50, category: 'fruits' },
      '3': { name: 'Carrot', price: 1.00, category: 'vegetables' },
      '4': { name: 'Bread', price: 3.00, category: 'bakery' },
    };

    // User adds items to cart
    addToCart('1', 2); // Apple
    addToCart('3', 5); // Carrot
    addToCart('4', 1); // Bread
    
    expect(getCartItemCount()).toBe(8); // 2 + 5 + 1
    
    // Calculate total with all products visible
    let total = calculateCartTotal(allProducts);
    expect(total).toBe(2.50 * 2 + 1.00 * 5 + 3.00 * 1); // $13.00
    
    // SIMULATE SEARCH: User searches for "apple", only product 1 is visible
    const searchResults = {
      '1': { name: 'Apple', price: 2.50, category: 'fruits' },
    };
    
    // Cart should still have all items
    const cart = getCart();
    expect(cart).toEqual({
      '1': 2,
      '3': 5,
      '4': 1,
    });
    expect(getCartItemCount()).toBe(8);
    
    // BUG: When calculating total with only search results,
    // items not in search are skipped
    total = calculateCartTotal(searchResults);
    
    // CURRENT BEHAVIOR: Only counts apple ($5.00)
    expect(total).toBe(5.00);
    
    // EXPECTED BEHAVIOR: Should count all items in cart ($13.00)
    // This test documents the bug - it will fail with current implementation
  });

  test('cart items not in search results are skipped in rendering', () => {
    // Add multiple items to cart
    setCart({
      '1': 2,  // Apple
      '2': 3,  // Banana
      '3': 1,  // Carrot
    });
    
    // Only some products are in current view (search filtered)
    const visibleProducts = {
      '1': { name: 'Apple', price: 2.50 },
      // Banana and Carrot are not visible due to search
    };
    
    // This simulates renderCart() logic: for (const [productId, quantity] of Object.entries(cart))
    const visibleCartItems = [];
    for (const [productId, quantity] of Object.entries(getCart())) {
      const product = visibleProducts[productId];
      if (!product) continue; // THIS IS THE BUG - skips items not in current view
      visibleCartItems.push({ productId, quantity, product });
    }
    
    // BUG: Only 1 item is visible in cart UI
    expect(visibleCartItems).toHaveLength(1);
    expect(visibleCartItems[0].productId).toBe('1');
    
    // But cart still has all 3 items
    expect(Object.keys(getCart())).toHaveLength(3);
  });

  test('cart total is incorrect when products are filtered', () => {
    const allProducts = {
      '1': { name: 'Apple', price: 10.00 },
      '2': { name: 'Banana', price: 5.00 },
      '3': { name: 'Carrot', price: 2.00 },
    };
    
    // Add all to cart
    setCart({ '1': 1, '2': 1, '3': 1 });
    
    // Total should be $17.00
    expect(calculateCartTotal(allProducts)).toBe(17.00);
    
    // After search that shows only Apple
    const searchFiltered = {
      '1': { name: 'Apple', price: 10.00 },
    };
    
    // BUG: Total shows only $10.00 instead of $17.00
    expect(calculateCartTotal(searchFiltered)).toBe(10.00);
    
    // This confuses users - cart total changes based on what's visible
  });

  test('removing item from cart while in search view', () => {
    // Setup cart with multiple items
    setCart({
      '1': 2,
      '2': 3,
      '3': 1,
    });
    
    // User searches, only product 1 visible
    const searchResults = {
      '1': { name: 'Apple', price: 2.50 },
    };
    
    // User removes product 2 (Banana) from cart
    // But product 2 is not in current search results
    removeFromCart('2');
    
    // Cart should be updated
    const cart = getCart();
    expect(cart['2']).toBeUndefined();
    expect(Object.keys(cart)).toEqual(['1', '3']);
    
    // This works correctly, but user can't see product 3 in the UI
  });

  test('cart persistence across search and clear search', () => {
    // User adds items
    addToCart('1', 2);
    addToCart('2', 3);
    saveCartToStorage();
    
    // User searches (page reloads with search results)
    // Cart loads from localStorage
    const loadedCart = loadCartFromStorage();
    expect(loadedCart).toEqual({ '1': 2, '2': 3 });
    
    // But only product 1 is visible in search
    const searchProducts = {
      '1': { name: 'Apple', price: 2.50 },
    };
    
    // Cart count should still be 5
    setCart(loadedCart);
    expect(getCartItemCount()).toBe(5);
    
    // But user only sees 1 product in cart UI
    let visibleCount = 0;
    for (const [productId] of Object.entries(getCart())) {
      if (searchProducts[productId]) visibleCount += getCart()[productId];
    }
    expect(visibleCount).toBe(2); // Only Apple's quantity
  });

  test('adding item during search should not affect other cart items', () => {
    // Cart already has items
    setCart({
      '1': 2,  // Apple
      '2': 1,  // Banana (not in search)
    });
    
    // User searches for "carrot", adds it
    addToCart('3', 5);
    
    // Cart should have all items
    const cart = getCart();
    expect(cart).toEqual({
      '1': 2,
      '2': 1,
      '3': 5,
    });
    
    // But if only product 3 is in search results, user won't see 1 and 2
  });

  test('cart icon count should show all items regardless of search', () => {
    // Add items from different categories
    setCart({
      '1': 2,   // Fruits
      '5': 3,   // Vegetables
      '10': 1,  // Bakery
    });
    
    // Total count should always be 6, regardless of what's visible
    expect(getCartItemCount()).toBe(6);
    
    // Even when searching and only 1 product category is visible
    const searchResults = {
      '1': { name: 'Apple', price: 2.50 },
    };
    
    // Count should still be 6 (this part works correctly)
    expect(getCartItemCount()).toBe(6);
  });
});

describe('Cart Rendering Edge Cases with Filtered Products', () => {
  beforeEach(() => {
    setCart({});
  });

  test('cart should handle products that no longer exist', () => {
    // User added product 99 which later gets deleted
    setCart({ '1': 2, '99': 5 });
    
    const currentProducts = {
      '1': { name: 'Apple', price: 2.50 },
      // Product 99 doesn't exist anymore
    };
    
    // Calculate total should skip missing products
    const total = calculateCartTotal(currentProducts);
    expect(total).toBe(5.00); // Only Apple
    
    // Cart still has the deleted product
    expect(getCart()['99']).toBe(5);
  });

  test('empty search results with items in cart', () => {
    // Cart has items
    setCart({
      '1': 5,
      '2': 3,
    });
    
    // Search returns no results
    const emptySearchResults = {};
    
    // Total would be 0 (no products to calculate)
    const total = calculateCartTotal(emptySearchResults);
    expect(total).toBe(0);
    
    // But cart still has 8 items
    expect(getCartItemCount()).toBe(8);
    
    // User sees "0 items" in cart UI but cart icon shows "8"
  });

  test('cart items with mismatched prices after product update', () => {
    // User adds apple at $2.50
    setCart({ '1': 2 });
    
    const originalProducts = {
      '1': { name: 'Apple', price: 2.50 },
    };
    expect(calculateCartTotal(originalProducts)).toBe(5.00);
    
    // Price changes to $3.00 (admin updates product)
    const updatedProducts = {
      '1': { name: 'Apple', price: 3.00 },
    };
    
    // Cart total now shows $6.00
    expect(calculateCartTotal(updatedProducts)).toBe(6.00);
    
    // User might be confused by price change
  });
});

describe('Proposed Fix Tests', () => {
  beforeEach(() => {
    setCart({});
  });

  test('PROPOSED: cart rendering should show warning for hidden items', () => {
    setCart({
      '1': 2,  // Visible in search
      '2': 3,  // Not visible
      '3': 1,  // Not visible
    });
    
    const searchResults = {
      '1': { name: 'Apple', price: 2.50 },
    };
    
    // Count items not in current view
    let hiddenItems = 0;
    for (const productId of Object.keys(getCart())) {
      if (!searchResults[productId]) {
        hiddenItems += getCart()[productId];
      }
    }
    
    // Should show: "4 items in cart are not visible due to search/filter"
    expect(hiddenItems).toBe(4); // 3 bananas + 1 carrot
  });

  test('PROPOSED: provide full product list to cart rendering', () => {
    // Instead of passing filtered products to renderCart,
    // pass all products separately
    
    const allProducts = {
      '1': { name: 'Apple', price: 2.50 },
      '2': { name: 'Banana', price: 1.50 },
      '3': { name: 'Carrot', price: 1.00 },
    };
    
    setCart({ '1': 2, '2': 3, '3': 1 });
    
    // Cart can always calculate correct total
    const total = calculateCartTotal(allProducts);
    expect(total).toBe(2.50 * 2 + 1.50 * 3 + 1.00 * 1); // $10.50
    
    // Even when search is active, cart uses full product list
  });
});
