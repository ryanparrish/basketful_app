/**
 * Cart Provider with react-use-cart
 * Integrates with backend validation
 */
import React, { createContext, useContext, useCallback, useMemo, useEffect, useState } from 'react';
import { CartProvider as ReactCartProvider, useCart as useReactCart } from 'react-use-cart';
import type { Product, CartItem as ApiCartItem } from '../shared/types/api';

// Extended cart item type
export interface CartItemData {
  id: string;
  name: string;
  price: number;
  quantity?: number;
  image?: string;
  category?: string;
  categoryId?: number;
  productId: number;
  unit?: string;
  available: boolean;
}

// Context for cart operations
interface CartContextType {
  items: CartItemData[];
  totalItems: number;
  cartTotal: number;
  isEmpty: boolean;
  addItem: (product: Product, quantity?: number) => void;
  removeItem: (id: string) => void;
  updateItemQuantity: (id: string, quantity: number) => void;
  clearCart: () => void;
  getItem: (id: string) => CartItemData | undefined;
  inCart: (id: string) => boolean;
  getApiCartItems: () => ApiCartItem[];
}

const CartContext = createContext<CartContextType | null>(null);

// Inner component that uses react-use-cart
const CartContextProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const {
    items,
    totalItems,
    cartTotal,
    isEmpty,
    addItem: addCartItem,
    removeItem: removeCartItem,
    updateItemQuantity: updateCartQuantity,
    emptyCart,
    getItem: getCartItem,
    inCart: isInCart,
  } = useReactCart();

  // Track hydration state
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Add product to cart
  const addItem = useCallback((product: Product, quantity = 1) => {
    const cartItem: CartItemData = {
      id: `product-${product.id}`,
      name: product.name,
      price: product.price || 0,
      quantity,
      image: product.image || undefined,
      category: product.category_name,
      categoryId: product.category,
      productId: product.id,
      unit: product.unit,
      available: product.is_available,
    };
    
    addCartItem(cartItem, quantity);
  }, [addCartItem]);

  // Remove item from cart
  const removeItem = useCallback((id: string) => {
    removeCartItem(id);
  }, [removeCartItem]);

  // Update item quantity
  const updateItemQuantity = useCallback((id: string, quantity: number) => {
    if (quantity <= 0) {
      removeCartItem(id);
    } else {
      updateCartQuantity(id, quantity);
    }
  }, [updateCartQuantity, removeCartItem]);

  // Clear entire cart
  const clearCart = useCallback(() => {
    emptyCart();
  }, [emptyCart]);

  // Get specific item
  const getItem = useCallback((id: string): CartItemData | undefined => {
    return getCartItem(id) as CartItemData | undefined;
  }, [getCartItem]);

  // Check if item is in cart
  const inCart = useCallback((id: string): boolean => {
    return isInCart(id);
  }, [isInCart]);

  // Convert to API format for validation/checkout
  const getApiCartItems = useCallback((): ApiCartItem[] => {
    return items.map(item => ({
      product_id: (item as CartItemData).productId,
      quantity: item.quantity || 1,
    }));
  }, [items]);

  const value = useMemo<CartContextType>(() => ({
    items: (isHydrated ? items : []) as CartItemData[],
    totalItems: isHydrated ? totalItems : 0,
    cartTotal: isHydrated ? cartTotal : 0,
    isEmpty: isHydrated ? isEmpty : true,
    addItem,
    removeItem,
    updateItemQuantity,
    clearCart,
    getItem,
    inCart,
    getApiCartItems,
  }), [items, totalItems, cartTotal, isEmpty, isHydrated, addItem, removeItem, updateItemQuantity, clearCart, getItem, inCart, getApiCartItems]);

  return (
    <CartContext.Provider value={value}>
      {children}
    </CartContext.Provider>
  );
};

// Main provider component
interface CartProviderProps {
  children: React.ReactNode;
}

export const CartProvider: React.FC<CartProviderProps> = ({ children }) => {
  return (
    <ReactCartProvider
      id="basketful-cart"
      onItemAdd={(item) => {
        console.log('Item added to cart:', item.id);
      }}
      onItemRemove={(item) => {
        console.log('Item removed from cart:', item?.id);
      }}
    >
      <CartContextProvider>
        {children}
      </CartContextProvider>
    </ReactCartProvider>
  );
};

// Hook to use cart
export const useCartContext = (): CartContextType => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCartContext must be used within a CartProvider');
  }
  return context;
};

// Helper hook to get item count for a specific product
export const useItemInCart = (productId: number) => {
  const { getItem, inCart } = useCartContext();
  const id = `product-${productId}`;
  const item = getItem(id);
  
  return {
    isInCart: inCart(id),
    quantity: item?.quantity || 0,
    item,
  };
};
