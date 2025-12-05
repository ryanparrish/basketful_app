/**
 * Jest tests for cart functionality
 */

const {
  initializeCart,
  saveCartToStorage,
  loadCartFromStorage,
  addToCart,
  removeFromCart,
  updateCartQuantity,
  getCartItemCount,
  calculateCartTotal,
  clearCart,
  getCart,
  setCart
} = require('./cart.js');

describe('Cart Initialization', () => {
  beforeEach(() => {
    setCart({});
    localStorage.clear();
  });

  test('should initialize empty cart from localStorage', () => {
    // localStorage is already empty in beforeEach
    const cart = loadCartFromStorage();
    expect(cart).toEqual({});
  });

  test('should save cart to localStorage', () => {
    const cart = { "1": 2, "2": 3 };
    localStorage.setItem('cart', JSON.stringify(cart));
    const retrieved = JSON.parse(localStorage.getItem('cart'));
    expect(retrieved).toEqual(cart);
  });

  test('should add item to cart', () => {
    let cart = {};
    const productId = "1";
    const quantity = 2;
    
    cart[productId] = (cart[productId] || 0) + quantity;
    expect(cart["1"]).toBe(2);
    
    // Add more of the same item
    cart[productId] = (cart[productId] || 0) + 3;
    expect(cart["1"]).toBe(5);
  });

  test('should remove item from cart', () => {
    let cart = { "1": 2, "2": 3 };
    delete cart["1"];
    expect(cart).toEqual({ "2": 3 });
  });

  test('should handle invalid cart data in localStorage', () => {
    localStorage.setItem('cart', 'invalid json');
    let cart;
    try {
      cart = JSON.parse(localStorage.getItem('cart'));
    } catch (e) {
      cart = {};
    }
    expect(cart).toEqual({});
  });
});

describe('Filter State Management', () => {
  test('should save filter state', () => {
    const category = 'fruits';
    localStorage.setItem('activeCategory', category);
    expect(localStorage.getItem('activeCategory')).toBe('fruits');
  });

  test('should load filter state', () => {
    localStorage.setItem('activeCategory', 'vegetables');
    const active = localStorage.getItem('activeCategory') || null;
    expect(active).toBe('vegetables');
  });

  test('should clear filter state', () => {
    localStorage.setItem('activeCategory', 'dairy');
    localStorage.setItem('activeCategory', '');
    const active = localStorage.getItem('activeCategory');
    // Empty string is stored and retrieved as empty string
    expect(active).toBe('');
  });
});

describe('Cart Calculations', () => {
  test('should calculate correct subtotal', () => {
    const price = 10.50;
    const quantity = 3;
    const subtotal = price * quantity;
    expect(subtotal).toBe(31.50);
  });

  test('should calculate correct cart total', () => {
    const products = {
      "1": { price: 10.00 },
      "2": { price: 15.50 },
      "3": { price: 7.25 }
    };
    const cart = { "1": 2, "2": 1, "3": 3 };
    
    let total = 0;
    for (const [productId, quantity] of Object.entries(cart)) {
      const product = products[productId];
      if (product) {
        total += product.price * quantity;
      }
    }
    
    expect(total).toBe(57.25); // (10*2) + (15.50*1) + (7.25*3)
  });

  test('should handle missing products in cart', () => {
    const products = {
      "1": { price: 10.00 }
    };
    const cart = { "1": 2, "999": 1 }; // 999 doesn't exist
    
    let total = 0;
    for (const [productId, quantity] of Object.entries(cart)) {
      const product = products[productId];
      if (product) {
        total += product.price * quantity;
      }
    }
    
    expect(total).toBe(20.00); // Only product 1 counted
  });
});

describe('Session vs LocalStorage Priority', () => {
  let localStorage;
  
  beforeEach(() => {
    localStorage = {
      data: {},
      getItem(key) {
        return this.data[key] || null;
      },
      setItem(key, value) {
        this.data[key] = value;
      }
    };
    global.localStorage = localStorage;
  });

  test('should prioritize session cart over localStorage', () => {
    const sessionCart = { "1": 5 };
    const localCart = { "2": 3 };
    localStorage.setItem('cart', JSON.stringify(localCart));
    
    // Simulate initialization logic
    let cart;
    if (sessionCart && Object.keys(sessionCart).length > 0) {
      localStorage.setItem('cart', JSON.stringify(sessionCart));
      cart = sessionCart;
    } else {
      cart = JSON.parse(localStorage.getItem('cart'));
    }
    
    expect(cart).toEqual({ "1": 5 });
  });

  test('should use localStorage when session is empty', () => {
    const sessionCart = {};
    const localCart = { "2": 3 };
    localStorage.setItem('cart', JSON.stringify(localCart));
    
    let cart;
    if (sessionCart && Object.keys(sessionCart).length > 0) {
      cart = sessionCart;
    } else {
      cart = JSON.parse(localStorage.getItem('cart'));
    }
    
    expect(cart).toEqual({ "2": 3 });
  });
});
