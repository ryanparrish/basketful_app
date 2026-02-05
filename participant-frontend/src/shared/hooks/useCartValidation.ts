/**
 * Cart Validation Hook
 * Provides easy access to validation state with product-specific helpers
 */
import { useMemo } from 'react';
import { useValidation, useCanCheckout } from '../../providers/ValidationContext';
import { useCartContext } from '../../providers/CartProvider';

export const useCartValidation = () => {
  const validation = useValidation();
  const { canCheckout, checkoutBlockedReason } = useCanCheckout();
  const { items, cartTotal, totalItems } = useCartContext();

  // Group errors by type
  const errorsByType = useMemo(() => {
    const grouped: Record<string, typeof validation.errors> = {};
    
    validation.errors.forEach(error => {
      const type = error.type || 'general';
      if (!grouped[type]) {
        grouped[type] = [];
      }
      grouped[type].push(error);
    });
    
    return grouped;
  }, [validation.errors]);

  // Check if there are budget-related errors
  const hasBudgetError = useMemo(() => {
    return validation.errors.some(e => 
      e.type === 'budget' || 
      e.type === 'over_budget' ||
      e.message?.toLowerCase().includes('budget')
    );
  }, [validation.errors]);

  // Check if there are quantity limit errors
  const hasQuantityError = useMemo(() => {
    return validation.errors.some(e => 
      e.type === 'quantity' || 
      e.type === 'limit' ||
      e.message?.toLowerCase().includes('limit')
    );
  }, [validation.errors]);

  // Check if there are availability errors
  const hasAvailabilityError = useMemo(() => {
    return validation.errors.some(e => 
      e.type === 'availability' || 
      e.message?.toLowerCase().includes('unavailable') ||
      e.message?.toLowerCase().includes('out of stock')
    );
  }, [validation.errors]);

  // Get remaining budget (if balances available)
  const remainingBudget = useMemo(() => {
    if (!validation.balances) return null;
    return validation.balances.remaining_budget;
  }, [validation.balances]);

  // Check if cart is over budget
  const isOverBudget = useMemo(() => {
    if (remainingBudget === null) return false;
    return cartTotal > remainingBudget;
  }, [cartTotal, remainingBudget]);

  // Get products with errors
  const productsWithErrors = useMemo(() => {
    const productIds = new Set<number>();
    validation.errors.forEach(error => {
      if (error.product_id) {
        productIds.add(error.product_id);
      }
    });
    return Array.from(productIds);
  }, [validation.errors]);

  // Get products with warnings
  const productsWithWarnings = useMemo(() => {
    const productIds = new Set<number>();
    validation.warnings.forEach(warning => {
      if (warning.product_id) {
        productIds.add(warning.product_id);
      }
    });
    return Array.from(productIds);
  }, [validation.warnings]);

  return {
    // State
    isValid: validation.isValid,
    isValidating: validation.isValidating,
    errors: validation.errors,
    warnings: validation.warnings,
    balances: validation.balances,
    programConfig: validation.programConfig,
    
    // Derived state
    canCheckout,
    checkoutBlockedReason,
    errorsByType,
    hasBudgetError,
    hasQuantityError,
    hasAvailabilityError,
    remainingBudget,
    isOverBudget,
    productsWithErrors,
    productsWithWarnings,
    
    // Cart info
    cartTotal,
    totalItems,
    items,
    
    // Actions
    revalidate: validation.revalidate,
    getErrorsForProduct: validation.getErrorsForProduct,
    getWarningsForProduct: validation.getWarningsForProduct,
    hasProductError: validation.hasProductError,
  };
};
