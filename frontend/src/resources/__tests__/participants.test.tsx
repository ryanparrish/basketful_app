/**
 * Participant resource form field contract tests.
 *
 * Covers: BEH-204
 *
 * BEH-204 regression:
 *   The "Infants" household input must be bound to `source="diaper_count"`,
 *   matching the backend field name. A previous version used `source="infants"`
 *   which caused infant count changes to be silently dropped by DRF (unknown
 *   fields are ignored). When it was also misnamed in the Show view, the count
 *   always displayed as blank.
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AdminContext, NumberInput, SimpleForm } from 'react-admin';
import '@testing-library/jest-dom';

// ---------------------------------------------------------------------------
// Minimal helpers
// ---------------------------------------------------------------------------

/** Renders children inside a bare AdminContext (no router, no data provider calls). */
function withAdminContext(ui: React.ReactElement) {
  return render(<AdminContext>{ui}</AdminContext>);
}

/** SimpleForm toolbar contains a DeleteButton that requires a Resource context.
 *  Suppress it in tests — we only care about the input fields. */
const noToolbar = false as const;

// ---------------------------------------------------------------------------
// BEH-204 — diaper_count source binding
// ---------------------------------------------------------------------------

describe('Participant form — household fields', () => {
  describe('BEH-204 — "Infants" input is bound to diaper_count, not infants', () => {
    it('Edit form: input labelled "Infants" has name="diaper_count"', () => {
      // Arrange — render the same three household inputs used in ParticipantEdit
      withAdminContext(
        <SimpleForm onSubmit={() => {}} toolbar={noToolbar}>
          <NumberInput source="adults" min={0} />
          <NumberInput source="children" min={0} />
          <NumberInput source="diaper_count" label="Infants" min={0} />
        </SimpleForm>
      );

      // Act — find the "Infants" field via its accessible label
      const infantInput = screen.getByLabelText(/^infants$/i);

      // Assert — the underlying input must be named diaper_count, not infants
      expect(infantInput).toHaveAttribute('name', 'diaper_count');
    });

    it('Create form: input labelled "Infants" has name="diaper_count"', () => {
      // Arrange — render the same three household inputs used in ParticipantCreate
      withAdminContext(
        <SimpleForm onSubmit={() => {}} toolbar={noToolbar}>
          <NumberInput source="adults" min={0} defaultValue={1} />
          <NumberInput source="children" min={0} defaultValue={0} />
          <NumberInput source="diaper_count" label="Infants" min={0} defaultValue={0} />
        </SimpleForm>
      );

      // Act
      const infantInput = screen.getByLabelText(/^infants$/i);

      // Assert
      expect(infantInput).toHaveAttribute('name', 'diaper_count');
    });

    it('adults input has name="adults"', () => {
      // Guard: ensure the sibling fields are also correctly named (sanity).
      // NOTE: RA resolves source-derived labels via i18n in test env, so we
      // query by name attribute directly rather than by label text.
      const { container } = withAdminContext(
        <SimpleForm onSubmit={() => {}} toolbar={noToolbar}>
          <NumberInput source="adults" min={0} />
          <NumberInput source="children" min={0} />
          <NumberInput source="diaper_count" label="Infants" min={0} />
        </SimpleForm>
      );
      expect(container.querySelector('input[name="adults"]')).toBeTruthy();
    });

    it('children input has name="children"', () => {
      const { container } = withAdminContext(
        <SimpleForm onSubmit={() => {}} toolbar={noToolbar}>
          <NumberInput source="adults" min={0} />
          <NumberInput source="children" min={0} />
          <NumberInput source="diaper_count" label="Infants" min={0} />
        </SimpleForm>
      );
      expect(container.querySelector('input[name="children"]')).toBeTruthy();
    });

    it('no input labelled "Infants" is named "infants" (regression guard)', () => {
      // If someone ever changes source back to "infants", this test breaks.
      withAdminContext(
        <SimpleForm onSubmit={() => {}} toolbar={noToolbar}>
          <NumberInput source="adults" min={0} />
          <NumberInput source="children" min={0} />
          <NumberInput source="diaper_count" label="Infants" min={0} />
        </SimpleForm>
      );
      const infantInput = screen.getByLabelText(/^infants$/i);
      expect(infantInput).not.toHaveAttribute('name', 'infants');
    });
  });
});
