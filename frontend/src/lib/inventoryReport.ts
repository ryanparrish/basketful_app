/**
 * Inventory report helpers (Issue #143), shared by the React page and its
 * tests. The report itself is computed by GET /api/v1/reports/inventory/.
 */

export type DateRangeChoice =
  | 'last_6_months'
  | 'this_week'
  | 'this_month'
  | 'last_month'
  | 'this_year'
  | 'custom';

export type Grouping = 'range' | 'weekly' | 'monthly';

export interface InventoryReportFilters {
  date_range: DateRangeChoice;
  start_date: string; // YYYY-MM-DD, used only for 'custom'
  end_date: string;
  program: string; // '' = all programs
  grouping: Grouping;
}

export interface InventoryItemRow {
  period_key: string;
  period_label: string;
  product_name: string;
  category: string;
  subcategory: string;
  quantity: number;
  total_cost: string;
}

export interface ProgramCostRow {
  period_key: string;
  period_label: string;
  program_name: string;
  total_cost: string;
}

export interface ParticipantWeekRow {
  week_start: string;
  week_end: string;
  counted_from: string;
  counted_to: string;
  is_partial: boolean;
  participant_count: number;
}

export interface InventoryReport {
  start_date: string;
  end_date: string;
  grouping: Grouping;
  program: number | null;
  program_name: string | null;
  counted_statuses: string[];
  items: InventoryItemRow[];
  program_costs: ProgramCostRow[];
  grand_total: string;
  participants_per_week: ParticipantWeekRow[];
}

export const DATE_RANGE_OPTIONS: { value: DateRangeChoice; label: string }[] = [
  { value: 'last_6_months', label: 'Last 6 Months' },
  { value: 'this_week', label: 'This Week' },
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'this_year', label: 'This Year' },
  { value: 'custom', label: 'Custom Range' },
];

export const GROUPING_OPTIONS: { value: Grouping; label: string }[] = [
  { value: 'range', label: 'Whole Range' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
];

export const DEFAULT_FILTERS: InventoryReportFilters = {
  date_range: 'last_6_months',
  start_date: '',
  end_date: '',
  program: '',
  grouping: 'range',
};

/** Query parameters for the API: custom dates only when the range is custom. */
export const buildReportParams = (
  filters: InventoryReportFilters,
): Record<string, string> => {
  const params: Record<string, string> = {
    date_range: filters.date_range,
    grouping: filters.grouping,
  };
  if (filters.date_range === 'custom') {
    if (filters.start_date) params.start_date = filters.start_date;
    if (filters.end_date) params.end_date = filters.end_date;
  }
  if (filters.program) params.program = filters.program;
  return params;
};

/** "2026-11-02" → "Nov 2, 2026", without timezone shifts. */
export const formatDate = (iso: string): string => {
  const [year, month, day] = iso.split('-').map(Number);
  if (!year || !month || !day) return iso;
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
};

export const formatMoney = (value: string): string => {
  const amount = Number(value);
  if (Number.isNaN(amount)) return value;
  return amount.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
};

/** The server's validation message(s) instead of axios's generic text. */
export const reportErrorMessage = (error: unknown): string => {
  const err = error as { response?: { data?: unknown }; message?: string };
  const data = err?.response?.data;
  if (data && typeof data === 'object' && !(data instanceof Blob)) {
    const parts = Object.values(data as Record<string, unknown>).map((msgs) =>
      Array.isArray(msgs) ? msgs.join(' ') : String(msgs),
    );
    if (parts.length) return parts.join(' ');
  }
  return err?.message || 'Could not load the report.';
};

/** Filename from a Content-Disposition header, with a sensible fallback. */
export const filenameFromDisposition = (
  header: string | undefined,
  fallback = 'inventory_report.csv',
): string => {
  const match = header?.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
};
