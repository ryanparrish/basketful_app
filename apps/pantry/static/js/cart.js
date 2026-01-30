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
  
  // Send cart to server and get updated balances
  syncCartWithServer(cartData || cart);
}

/**
 * Sync cart with server and update balance display
 */
function syncCartWithServer(cartData) {
  const csrftoken = getCookie('csrftoken');
  
  fetch('/update-cart/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrftoken
    },
    body: JSON.stringify(cartData)
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === 'ok' && data.balances) {
      updateCartBalances(data.balances);
    }
  })
  .catch(error => {
    console.error('Error syncing cart:', error);
  });
}

/**
 * Update balance display in cart drawer
 */
function updateCartBalances(balances) {
  // Format balances with dollar sign and 2 decimals
  const formatBalance = (balance) => {
    const num = parseFloat(balance);
    return isNaN(num) ? '$0.00' : `$${num.toFixed(2)}`;
  };
  
  // Update balance elements if they exist
  const availableBalanceEl = document.getElementById('cart-available-balance');
  const hygieneBalanceEl = document.getElementById('cart-hygiene-balance');
  const goFreshBalanceEl = document.getElementById('cart-go-fresh-balance');
  
  if (availableBalanceEl) {
    availableBalanceEl.textContent = formatBalance(balances.available_balance);
  }
  if (hygieneBalanceEl) {
    hygieneBalanceEl.textContent = formatBalance(balances.hygiene_balance);
  }
  if (goFreshBalanceEl) {
    goFreshBalanceEl.textContent = formatBalance(balances.go_fresh_balance);
  }
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
  // Validate product ID
  if (!productId || productId === 'undefined' || productId === 'null') {
    console.error('Invalid product ID');
    return false;
  }
  
  // Validate quantity is a number
  if (typeof quantity !== 'number') {
    console.error('Quantity must be a number, got:', typeof quantity);
    return false;
  }
  
  // Check for NaN
  if (isNaN(quantity)) {
    console.error('Quantity cannot be NaN');
    return false;
  }
  
  // Check for Infinity
  if (!Number.isFinite(quantity)) {
    console.error('Quantity must be finite');
    return false;
  }
  
  // Round to integer (reject floats)
  quantity = Math.round(quantity);
  
  // Check positive
  if (quantity <= 0) {
    console.error('Quantity must be positive');
    return false;
  }
  
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
    if (product && typeof product.price === 'number' && !isNaN(product.price)) {
      total += product.price * quantity;
    } else {
      console.warn(`Product ${productId} has no valid price, skipping in total`);
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
