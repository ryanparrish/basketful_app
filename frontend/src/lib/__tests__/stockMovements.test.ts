import { describe, expect, it } from 'vitest';
import { stockMovementErrorMessage, validateQuantityChange } from '../stockMovements';

describe('validateQuantityChange', () => {
  it('accepts a positive receiving and a negative spoilage', () => {
    expect(validateQuantityChange(24, { kind: 'received' })).toBeUndefined();
    expect(validateQuantityChange(-3, { kind: 'spoilage' })).toBeUndefined();
  });

  it('allows corrections either way', () => {
    expect(validateQuantityChange(5, { kind: 'correction' })).toBeUndefined();
    expect(validateQuantityChange(-5, { kind: 'correction' })).toBeUndefined();
  });

  it('rejects zero and fractions', () => {
    expect(validateQuantityChange(0, { kind: 'correction' })).toMatch(/not zero/);
    expect(validateQuantityChange(1.5, { kind: 'received' })).toMatch(/whole number/);
  });

  it('rejects a sign that does not match the kind', () => {
    expect(validateQuantityChange(-3, { kind: 'received' })).toMatch(/must be positive/);
    expect(validateQuantityChange(-3, { kind: 'donation' })).toMatch(/must be positive/);
    expect(validateQuantityChange(3, { kind: 'spoilage' })).toMatch(/negative/);
  });

  it('leaves an empty value to required()', () => {
    expect(validateQuantityChange('', { kind: 'received' })).toBeUndefined();
  });
});

describe('stockMovementErrorMessage', () => {
  it("shows the server's field message instead of axios's generic one", () => {
    const error = {
      message: 'Request failed with status code 400',
      response: {
        data: {
          quantity_change: [
            'This movement would take Rice below zero (current stock: 5, change: -6).',
          ],
        },
      },
    };
    expect(stockMovementErrorMessage(error)).toBe(
      'This movement would take Rice below zero (current stock: 5, change: -6).',
    );
  });

  it('falls back to the error message', () => {
    expect(stockMovementErrorMessage({ message: 'Network Error' })).toBe('Network Error');
  });
});
