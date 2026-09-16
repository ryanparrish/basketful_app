/**
 * Cart Management Module
 * Extracted from create_order.html for testing
 */

// A local cart younger than this survives a session cart that looks empty
// (a reload or back-swipe racing ahead of syncCartToServer). Older than
// this, it's treated as genuinely abandoned and dropped — this is what
// stops a stale cart from resurrecting the way it did before the fix in
// commit c23d6a7. 30 minutes: OWASP's Session Management Cheat Sheet puts
// idle timeouts for low-risk applications at 15-30 minutes, and cart
// abandonment research treats ~30-60 minutes as the point a cart shifts
// from "still shopping" to "abandoned but recoverable" — this sits at the
// intersection of both.
const CART_TTL_MS = 30 * 60 * 1000;

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
 * localStorage key for a cart, scoped to cartToken when given. Scoping by
 * a per-session token means a shared/kiosk device never hands one
 * participant's leftover cart to the next person who logs in on it.
 */
function cartStorageKey(cartToken) {
  return cartToken ? `cart:${cartToken}` : 'cart';
}

function cartTimestampKey(cartToken) {
  return `${cartStorageKey(cartToken)}:updatedAt`;
}

function isLocalCartFresh(cartToken) {
  const updatedAt = Number(localStorage.getItem(cartTimestampKey(cartToken)) || 0);
  return updatedAt > 0 && (Date.now() - updatedAt) < CART_TTL_MS;
}

/**
 * Initialize cart from session or localStorage.
 *
 * A non-empty sessionCart is always authoritative — the browser already
 * synced it, or checkout just cleared it server-side.
 *
 * An empty sessionCart is ambiguous: "nothing added yet", "just checked
 * out", or "a reload/back-swipe raced ahead of the last add/remove's
 * sync". Recover a *fresh* local cart (see CART_TTL_MS) rather than
 * assume abandonment; anything older is dropped, same as before.
 *
 * sessionCart === null means no server signal was provided at all
 * (defensive/legacy call sites) — fall back to localStorage unconditionally.
 */
function initializeCart(sessionCart, cartToken) {
  if (sessionCart != null && Object.keys(sessionCart).length > 0) {
    localStorage.setItem(cartStorageKey(cartToken), JSON.stringify(sessionCart));
    localStorage.setItem(cartTimestampKey(cartToken), String(Date.now()));
    return sessionCart;
  }

  if (sessionCart === null) {
    return loadCartFromStorage(cartToken);
  }

  if (isLocalCartFresh(cartToken)) {
    const localCart = loadCartFromStorage(cartToken);
    if (Object.keys(localCart).length > 0) {
      syncCartWithServer(localCart).catch(error => {
        console.error('Error re-syncing recovered cart:', error);
      });
      return localCart;
    }
  }

  localStorage.setItem(cartStorageKey(cartToken), JSON.stringify({}));
  localStorage.setItem(cartTimestampKey(cartToken), String(Date.now()));
  return {};
}

/**
 * Save cart to localStorage
 */
function saveCartToStorage(cartData, cartToken) {
  const data = cartData || cart;
  localStorage.setItem(cartStorageKey(cartToken), JSON.stringify(data));
  localStorage.setItem(cartTimestampKey(cartToken), String(Date.now()));

  // Send cart to server and get updated balances
  syncCartWithServer(data).catch(error => {
    console.error('Error syncing cart:', error);
  });
}

/**
 * Sync cart with server and update balance display. Returns the fetch
 * promise so callers that need to know success/failure (e.g. before
 * redirecting to checkout) can chain their own .then()/.catch() — callers
 * that don't care can fire-and-forget with their own .catch(console.error).
 */
function syncCartWithServer(cartData) {
  const csrftoken = getCookie('csrftoken');

  return fetch('/update-cart/', {
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
    return data;
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
function loadCartFromStorage(cartToken) {
  try {
    const stored = localStorage.getItem(cartStorageKey(cartToken));
    return stored ? JSON.parse(stored) : {};
  } catch (e) {
    console.warn("Cart data in localStorage is invalid.");
    return {};
  }
}

/**
 * Add item to cart
 */
function addToCart(productId, quantity, cartToken) {
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
  saveCartToStorage(cart, cartToken);
  return true;
}

/**
 * Remove item from cart
 */
function removeFromCart(productId, cartToken) {
  delete cart[productId];
  saveCartToStorage(cart, cartToken);
}

/**
 * Update item quantity in cart
 */
function updateCartQuantity(productId, quantity, cartToken) {
  if (quantity <= 0) {
    removeFromCart(productId, cartToken);
  } else {
    cart[productId] = quantity;
    saveCartToStorage(cart, cartToken);
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
function clearCart(cartToken) {
  cart = {};
  saveCartToStorage(cart, cartToken);
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
    CART_TTL_MS,
    getCookie,
    cartStorageKey,
    cartTimestampKey,
    isLocalCartFresh,
    initializeCart,
    saveCartToStorage,
    syncCartWithServer,
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
