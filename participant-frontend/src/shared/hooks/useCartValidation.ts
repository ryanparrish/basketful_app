/**
 * Cart Validation Hook
 * Provides easy access to validation state with product-specific helpers
 */
import { useMemo } from 'react';
import { useValidation, useCanCheckout } from '../../providers/ValidationContext';
import { useCartContext } from '../../providers/CartProvider';

export const useCartValidation = () => {
  const validation = useValidation();
  const { canCheckout, checkoutBlockedReasonKey } = useCanCheckout();
  const { items, cartTotal, totalItems } = useCartContext();

  // Bucket errors by the backend's machine-readable type — never by
  // message text, which is locale-dependent
  const hasBudgetError = useMemo(
    () => validation.errors.some(e => e.type === 'balance'),
    [validation.errors]
  );

  const hasQuantityError = useMemo(
    () => validation.errors.some(e => e.type === 'limit'),
    [validation.errors]
  );

  // Get remaining budget computed client-side so it updates instantly as cart changes.
  // available_balance is the participant's static account balance; subtract cartTotal for live display.
  const remainingBudget = useMemo(() => {
    if (!validation.balances) return null;
    return Math.max(0, validation.balances.available_balance - cartTotal);
  }, [validation.balances, cartTotal]);

  // Check if cart is over budget — compare directly against available_balance,
  // not the already-subtracted remainder (which would fire at half the balance).
  const isOverBudget = useMemo(() => {
    if (!validation.balances) return false;
    return cartTotal > validation.balances.available_balance;
  }, [cartTotal, validation.balances]);

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
    checkoutBlockedReasonKey,
    hasBudgetError,
    hasQuantityError,
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
