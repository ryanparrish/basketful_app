import { useState, useEffect } from 'react';

/**
 * Debounce a value by the given delay in milliseconds.
 * Returns the debounced value, which only updates after the delay
 * has elapsed with no new value changes.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
