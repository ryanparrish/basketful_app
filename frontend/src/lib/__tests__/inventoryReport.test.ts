import { describe, expect, it } from 'vitest';
import {
  DEFAULT_FILTERS,
  buildReportParams,
  filenameFromDisposition,
  formatDate,
  formatMoney,
  reportErrorMessage,
} from '../inventoryReport';

describe('buildReportParams', () => {
  it('sends only the range and grouping by default', () => {
    expect(buildReportParams(DEFAULT_FILTERS)).toEqual({
      date_range: 'last_6_months',
      grouping: 'range',
    });
  });

  it('includes custom dates only for a custom range', () => {
    const custom = { ...DEFAULT_FILTERS, date_range: 'custom' as const, start_date: '2026-11-02', end_date: '2026-11-08' };
    expect(buildReportParams(custom)).toMatchObject({ start_date: '2026-11-02', end_date: '2026-11-08' });
    const preset = { ...custom, date_range: 'this_month' as const };
    expect(buildReportParams(preset)).not.toHaveProperty('start_date');
  });

  it('includes the program when one is picked', () => {
    expect(buildReportParams({ ...DEFAULT_FILTERS, program: '3' })).toMatchObject({ program: '3' });
  });
});

describe('formatting', () => {
  it('formats ISO dates without shifting the day', () => {
    expect(formatDate('2026-11-02')).toBe('Nov 2, 2026');
  });

  it('formats money strings as dollars', () => {
    expect(formatMoney('22.5')).toBe('$22.50');
    expect(formatMoney('1234.00')).toBe('$1,234.00');
  });
});

describe('reportErrorMessage', () => {
  it("shows the server's validation message", () => {
    const error = { message: 'Request failed', response: { data: { end_date: ['End date must be on or after the start date.'] } } };
    expect(reportErrorMessage(error)).toBe('End date must be on or after the start date.');
  });

  it('falls back to the error message', () => {
    expect(reportErrorMessage({ message: 'Network Error' })).toBe('Network Error');
  });
});

describe('filenameFromDisposition', () => {
  it('reads the server filename', () => {
    expect(filenameFromDisposition('attachment; filename="inventory_report_2026-05-21_2026-11-21.csv"'))
      .toBe('inventory_report_2026-05-21_2026-11-21.csv');
  });

  it('falls back when missing', () => {
    expect(filenameFromDisposition(undefined)).toBe('inventory_report.csv');
  });
});
