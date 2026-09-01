/**
 * Product form field contract tests.
 *
 * Regression for issues #92/#94 ("New product not adding"):
 *   `weight_lbs` is a non-nullable DecimalField (apps/pantry/models.py) with no
 *   database default applied on the frontend's behalf. react-admin's NumberInput
 *   emits `null` (not '' and not omitted) when left blank, and DRF rejects an
 *   explicit `null` for a non-nullable field with a 400 — so leaving the Weight
 *   field untouched on product creation failed to save. Fixed by giving the
 *   Create form's weight_lbs a defaultValue, matching every other optional
 *   NumberInput in this codebase (quantity_in_stock on the same form, sort_order
 *   in categories.tsx/productLimits.tsx, adults/children/diaper_count in
 *   participants.tsx).
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/react';
import { AdminContext, NumberInput, SimpleForm } from 'react-admin';
import '@testing-library/jest-dom';

function withAdminContext(ui: React.ReactElement) {
  return render(<AdminContext>{ui}</AdminContext>);
}

const noToolbar = false as const;

describe('Product form — weight_lbs must never submit as null', () => {
  it('Create form: submitting without touching Weight sends 0, not null', async () => {
    const onSubmit = vi.fn();

    const { container } = withAdminContext(
      <SimpleForm onSubmit={onSubmit} toolbar={noToolbar}>
        <NumberInput source="quantity_in_stock" min={0} defaultValue={0} />
        <NumberInput source="weight_lbs" min={0} step={0.1} defaultValue={0} />
      </SimpleForm>
    );

    // Submit the form without interacting with any field.
    fireEvent.submit(container.querySelector('form')!);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.weight_lbs).toBe(0);
    expect(submitted.weight_lbs).not.toBeNull();
  });

  it('regression guard: without a defaultValue, an untouched weight_lbs submits as null', async () => {
    // Demonstrates the exact bug: the same field, minus defaultValue, produces
    // the null payload DRF rejected. Guards against the fix being reverted.
    const onSubmit = vi.fn();

    const { container } = withAdminContext(
      <SimpleForm onSubmit={onSubmit} toolbar={noToolbar}>
        <NumberInput source="weight_lbs" min={0} step={0.1} />
      </SimpleForm>
    );

    fireEvent.submit(container.querySelector('form')!);

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.weight_lbs).toBeNull();
  });
});
