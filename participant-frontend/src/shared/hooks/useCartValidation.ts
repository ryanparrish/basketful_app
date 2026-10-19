/**
 * Cart Validation Hook
 * Provides easy access to validation state with product-specific helpers
 */
import { useMemo } from 'react';
import { useValidation, useCanCheckout } from '../../providers/ValidationContext';
import { useCartContext } from '../../providers/CartProvider';
import { useBudgets } from './useBudgets';

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

  // Food balance left, computed client-side so it updates instantly as the
  // cart changes. Hygiene and Go Fresh items don't draw from it — see useBudgets.
  const budgets = useBudgets();
  const remainingBudget = budgets ? budgets.food.remaining : null;

  // Over budget if ANY balance is exceeded (hygiene and Go Fresh included).
  const isOverBudget = budgets?.isOverAny ?? false;

  // Get products with errors
  const productsWithErrors = useMemo(
    () => Array.from(new Set(validation.errors.flatMap(e => e.product_ids ?? []))),
    [validation.errors]
  );

  // Get products with warnings
  const productsWithWarnings = useMemo(
    () => Array.from(new Set(validation.warnings.flatMap(w => w.product_ids ?? []))),
    [validation.warnings]
  );

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
