/**
 * Stock forecast helpers (Issue #148), shared by the Stock Forecast page,
 * the products list column and the product usage panel. The forecast
 * itself is computed by GET /api/v1/reports/stock-forecast/.
 */

export type ForecastStatus = 'critical' | 'low' | 'ok' | 'insufficient_history';

export interface ForecastWeek {
  week_start: string;
  units: number;
  usable: boolean;
  excluded_reason: string;
}

export interface ForecastRow {
  product_id: number;
  product_name: string;
  category: string;
  active: boolean;
  quantity_in_stock: number;
  pending_units: number;
  available: number;
  usable_weeks: number;
  weekly_usage: number | null;
  weeks_left: number | null;
  runout_date: string | null;
  suggested_reorder: number | null;
  status: ForecastStatus;
  last_received_at: string | null;
  explanation: string;
  history: ForecastWeek[];
}

export interface ForecastResponse {
  generated_on: string;
  history_weeks: number;
  cover_weeks: number;
  safety_weeks: number;
  min_usable_weeks: number;
  results: ForecastRow[];
}

export interface ForecastSettings {
  history_weeks: number;
  cover_weeks: number;
  safety_weeks: number;
  category: string; // '' = all
  status: '' | ForecastStatus;
}

export const DEFAULT_FORECAST_SETTINGS: ForecastSettings = {
  history_weeks: 12,
  cover_weeks: 4,
  safety_weeks: 1,
  category: '',
  status: '',
};

type ChipColor = 'error' | 'warning' | 'success' | 'default';

export const STATUS_META: Record<ForecastStatus, { label: string; color: ChipColor; description: string }> = {
  critical: {
    label: 'Order now',
    color: 'error',
    description: 'Runs out within the safety window',
  },
  low: {
    label: 'Running low',
    color: 'warning',
    description: 'Runs out within the cover window',
  },
  ok: { label: 'OK', color: 'success', description: 'Enough stock for the cover window' },
  insufficient_history: {
    label: 'Not enough history',
    color: 'default',
    description: 'Fewer usable weeks than needed to forecast',
  },
};

export const STATUS_OPTIONS: { value: '' | ForecastStatus; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'critical', label: STATUS_META.critical.label },
  { value: 'low', label: STATUS_META.low.label },
  { value: 'ok', label: STATUS_META.ok.label },
  { value: 'insufficient_history', label: STATUS_META.insufficient_history.label },
];

/** Query parameters for the API; filters only when set. */
export const buildForecastParams = (settings: ForecastSettings): Record<string, string> => {
  const params: Record<string, string> = {
    history_weeks: String(settings.history_weeks),
    cover_weeks: String(settings.cover_weeks),
    safety_weeks: String(settings.safety_weeks),
  };
  if (settings.category) params.category = settings.category;
  if (settings.status) params.status = settings.status;
  return params;
};

/** "3.5 weeks", "1 week", "<1 day", or "—" when there's no demand. */
export const formatWeeksLeft = (weeks: number | null): string => {
  if (weeks === null || weeks === undefined) return '—';
  if (weeks <= 0) return 'Out';
  if (weeks < 1 / 7) return '<1 day';
  if (weeks < 1) {
    const days = Math.round(weeks * 7);
    return `${days} day${days === 1 ? '' : 's'}`;
  }
  return `${weeks} week${weeks === 1 ? '' : 's'}`;
};

/** "2026-12-03" → "Dec 3", without timezone shifts. */
export const formatShortDate = (iso: string | null): string => {
  if (!iso) return '—';
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number);
  if (!year || !month || !day) return iso;
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
};

/** The server's validation message(s) instead of axios's generic text. */
export const forecastErrorMessage = (error: unknown): string => {
  const err = error as { response?: { data?: unknown }; message?: string };
  const data = err?.response?.data;
  if (data && typeof data === 'object' && !(data instanceof Blob)) {
    const parts = Object.values(data as Record<string, unknown>).map((msgs) =>
      Array.isArray(msgs) ? msgs.join(' ') : String(msgs),
    );
    if (parts.length) return parts.join(' ');
  }
  return err?.message || 'Could not load the forecast.';
};

/** Bar heights (0-100) for the weekly usage panel. */
export const barHeights = (history: ForecastWeek[]): number[] => {
  const peak = Math.max(1, ...history.map((w) => w.units));
  return history.map((w) => Math.round((w.units / peak) * 100));
};
