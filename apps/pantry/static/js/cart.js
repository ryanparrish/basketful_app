/**
 * Cart Management Module
 * Extracted from create_order.html for testing
 */

// Cart state
let cart = {};

/**
 * Get CSRF token from cookie
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    for (let cookie of document.cookie.split(';')) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.slice(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Initialize cart from session or localStorage
 */
function initializeCart(sessionCart) {
  if (sessionCart && Object.keys(sessionCart).length > 0) {
    localStorage.setItem('cart', JSON.stringify(sessionCart));
    return sessionCart;
  }
  return loadCartFromStorage();
}

/**
 * Save cart to localStorage
 */
function saveCartToStorage(cartData) {
  localStorage.setItem('cart', JSON.stringify(cartData || cart));
}

/**
 * Load cart from localStorage
 */
function loadCartFromStorage() {
  try {
    const stored = localStorage.getItem('cart');
    return stored ? JSON.parse(stored) : {};
  } catch (e) {
    console.warn("Cart data in localStorage is invalid.");
    return {};
  }
}

/**
 * Add item to cart
 */
function addToCart(productId, quantity) {
  if (quantity <= 0) return false;
  
  cart[productId] = (cart[productId] || 0) + quantity;
  saveCartToStorage(cart);
  return true;
}

/**
 * Remove item from cart
 */
function removeFromCart(productId) {
  delete cart[productId];
  saveCartToStorage(cart);
}

/**
 * Update item quantity in cart
 */
function updateCartQuantity(productId, quantity) {
  if (quantity <= 0) {
    removeFromCart(productId);
  } else {
    cart[productId] = quantity;
    saveCartToStorage(cart);
  }
}

/**
 * Get cart total count
 */
function getCartItemCount() {
  return Object.values(cart).reduce((sum, qty) => sum + qty, 0);
}

/**
 * Calculate cart total price
 */
function calculateCartTotal(products) {
  let total = 0;
  for (const [productId, quantity] of Object.entries(cart)) {
    const product = products[productId];
    if (product) {
      total += product.price * quantity;
    }
  }
  return total;
}

/**
 * Clear entire cart
 */
function clearCart() {
  cart = {};
  saveCartToStorage(cart);
}

/**
 * Get current cart state
 */
function getCart() {
  return { ...cart };
}

/**
 * Set cart state (useful for testing)
 */
function setCart(newCart) {
  cart = { ...newCart };
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    getCookie,
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
  };
}
