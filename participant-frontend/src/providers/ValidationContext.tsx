/**
 * Validation Context
 * Manages backend cart validation with debouncing and caching
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCartContext } from './CartProvider';
import { validateCart, getProgramConfig, getBalances } from '../shared/api/endpoints';
import { useOrderWindow } from '../shared/hooks/useOrderWindow';
import type { ProgramConfig, Balances, ValidationError } from '../shared/types/api';

interface ValidationState {
  isValid: boolean;
  isValidating: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  balances: Balances | null;
  programConfig: ProgramConfig | null;
  ruleVersion: number | null;
  lastValidated: Date | null;
}

interface ValidationContextType extends ValidationState {
  revalidate: () => Promise<void>;
  getErrorsForProduct: (productId: number) => ValidationError[];
  getWarningsForProduct: (productId: number) => ValidationError[];
  hasProductError: (productId: number) => boolean;
  clearValidation: () => void;
}

const ValidationContext = createContext<ValidationContextType | null>(null);

const VALIDATION_DEBOUNCE_MS = 500;
const RULE_VERSION_POLL_INTERVAL = 60 * 1000; // 1 minute

interface ValidationProviderProps {
  children: React.ReactNode;
}

export const ValidationProvider: React.FC<ValidationProviderProps> = ({ children }) => {
  const queryClient = useQueryClient();
  const { items, getApiCartItems, isEmpty } = useCartContext();
  
  const [validationState, setValidationState] = useState<ValidationState>({
    isValid: true,
    isValidating: false,
    errors: [],
    warnings: [],
    balances: null,
    programConfig: null,
    ruleVersion: null,
    lastValidated: null,
  });

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastRuleVersionRef = useRef<number | null>(null);

  // Fetch program config
  const { data: programConfig } = useQuery({
    queryKey: ['programConfig'],
    queryFn: getProgramConfig,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: RULE_VERSION_POLL_INTERVAL,
  });

  // Fetch balances
  const { data: balances, refetch: refetchBalances } = useQuery({
    queryKey: ['balances'],
    queryFn: getBalances,
    staleTime: 30 * 1000, // 30 seconds
    refetchOnWindowFocus: true,
  });

  // Update state when program config or balances change
  useEffect(() => {
    if (programConfig || balances) {
      setValidationState(prev => ({
        ...prev,
        programConfig: programConfig || prev.programConfig,
        balances: balances || prev.balances,
        ruleVersion: programConfig?.rule_version || prev.ruleVersion,
      }));
    }
  }, [programConfig, balances]);

  // Check for rule version changes and revalidate
  useEffect(() => {
    if (programConfig?.rule_version && lastRuleVersionRef.current !== null) {
      if (programConfig.rule_version !== lastRuleVersionRef.current) {
        // Rules changed, force revalidation
        console.log('Rule version changed, revalidating cart...');
        performValidation();
      }
    }
    lastRuleVersionRef.current = programConfig?.rule_version || null;
  }, [programConfig?.rule_version]);

  // Perform cart validation
  const performValidation = useCallback(async () => {
    if (isEmpty) {
      setValidationState(prev => ({
        ...prev,
        isValid: true,
        isValidating: false,
        errors: [],
        warnings: [],
        lastValidated: new Date(),
      }));
      return;
    }

    setValidationState(prev => ({ ...prev, isValidating: true }));

    try {
      const cartItems = getApiCartItems();
      const response = await validateCart({ items: cartItems });
      
      setValidationState(prev => ({
        ...prev,
        isValid: response.valid,
        isValidating: false,
        errors: (response.violations || []).filter(v => v.severity !== 'warning'),
        warnings: (response.violations || []).filter(v => v.severity === 'warning'),
        lastValidated: new Date(),
      }));

      // Refetch balances after validation
      refetchBalances();
    } catch (error) {
      console.error('Validation error:', error);
      setValidationState(prev => ({
        ...prev,
        isValidating: false,
        // No message — components translate type 'system' at render time
        errors: [{ type: 'system', message: '' }],
      }));
    }
  }, [isEmpty, getApiCartItems, refetchBalances]);

  // Debounced validation when cart changes
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      performValidation();
    }, VALIDATION_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [items, performValidation]);

  // Manual revalidation
  const revalidate = useCallback(async () => {
    await performValidation();
    // Also invalidate related queries
    queryClient.invalidateQueries({ queryKey: ['balances'] });
    queryClient.invalidateQueries({ queryKey: ['programConfig'] });
  }, [performValidation, queryClient]);

  // Get errors for specific product
  const getErrorsForProduct = useCallback((productId: number): ValidationError[] => {
    return validationState.errors.filter(err => err.product_id === productId);
  }, [validationState.errors]);

  // Get warnings for specific product
  const getWarningsForProduct = useCallback((productId: number): ValidationError[] => {
    return validationState.warnings.filter(warn => warn.product_id === productId);
  }, [validationState.warnings]);

  // Check if product has error
  const hasProductError = useCallback((productId: number): boolean => {
    return validationState.errors.some(err => err.product_id === productId);
  }, [validationState.errors]);

  // Clear validation state
  const clearValidation = useCallback(() => {
    setValidationState(prev => ({
      ...prev,
      isValid: true,
      errors: [],
      warnings: [],
      lastValidated: null,
    }));
  }, []);

  const value = useMemo<ValidationContextType>(() => ({
    ...validationState,
    revalidate,
    getErrorsForProduct,
    getWarningsForProduct,
    hasProductError,
    clearValidation,
  }), [validationState, revalidate, getErrorsForProduct, getWarningsForProduct, hasProductError, clearValidation]);

  return (
    <ValidationContext.Provider value={value}>
      {children}
    </ValidationContext.Provider>
  );
};

export const useValidation = (): ValidationContextType => {
  const context = useContext(ValidationContext);
  if (!context) {
    throw new Error('useValidation must be used within a ValidationProvider');
  }
  return context;
};

/**
 * Why checkout is blocked, as an i18n key — consumers translate it so the
 * text follows the active language.
 */
export type CheckoutBlockedReasonKey =
  | 'validation.blocked.cartEmpty'
  | 'validation.blocked.validating'
  | 'validation.blocked.checkingWindow'
  | 'validation.blocked.windowForceClosed'
  | 'validation.blocked.windowDisabled'
  | 'validation.blocked.windowNoSchedule'
  | 'validation.blocked.windowClosed'
  | 'validation.blocked.fixCartErrors'
  | 'validation.blocked.cartInvalid';

// Hook to check if cart can be submitted
export const useCanCheckout = () => {
  const { isValid, isValidating, errors, balances, programConfig } = useValidation();
  const { isEmpty } = useCartContext();
  const { isOpen: windowIsOpen, windowStatus, isLoading: windowLoading } = useOrderWindow();

  const canCheckout = useMemo(() => {
    if (isEmpty) return false;
    if (isValidating) return false;
    if (windowLoading) return false;
    if (!windowIsOpen) return false;
    if (!isValid) return false;
    if (errors.length > 0) return false;
    return true;
  }, [isEmpty, isValidating, windowLoading, windowIsOpen, isValid, errors]);

  const checkoutBlockedReasonKey = useMemo((): CheckoutBlockedReasonKey | null => {
    if (isEmpty) return 'validation.blocked.cartEmpty';
    if (isValidating) return 'validation.blocked.validating';
    if (windowLoading) return 'validation.blocked.checkingWindow';
    if (!windowIsOpen) {
      if (windowStatus === 'force_closed') return 'validation.blocked.windowForceClosed';
      if (windowStatus === 'disabled') return 'validation.blocked.windowDisabled';
      if (windowStatus === 'no_schedule') return 'validation.blocked.windowNoSchedule';
      return 'validation.blocked.windowClosed';
    }
    if (errors.length > 0) return 'validation.blocked.fixCartErrors';
    if (!isValid) return 'validation.blocked.cartInvalid';
    return null;
  }, [isEmpty, isValidating, windowLoading, windowIsOpen, windowStatus, isValid, errors]);

  return {
    canCheckout,
    checkoutBlockedReasonKey,
    isValidating,
    balances,
    programConfig,
  };
};
