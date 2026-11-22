import { describe, expect, it } from 'vitest';
import {
  DEFAULT_FORECAST_SETTINGS,
  barHeights,
  buildForecastParams,
  forecastErrorMessage,
  formatShortDate,
  formatWeeksLeft,
} from '../stockForecast';

describe('buildForecastParams', () => {
  it('sends the defaults and no empty filters', () => {
    expect(buildForecastParams(DEFAULT_FORECAST_SETTINGS)).toEqual({
      history_weeks: '12',
      cover_weeks: '4',
      safety_weeks: '1',
    });
  });

  it('includes category and status when set', () => {
    expect(
      buildForecastParams({ ...DEFAULT_FORECAST_SETTINGS, category: '3', status: 'critical' }),
    ).toMatchObject({ category: '3', status: 'critical' });
  });
});

describe('formatWeeksLeft', () => {
  it('reads naturally', () => {
    expect(formatWeeksLeft(null)).toBe('—');
    expect(formatWeeksLeft(0)).toBe('Out');
    expect(formatWeeksLeft(0.1)).toBe('<1 day');
    expect(formatWeeksLeft(0.5)).toBe('4 days');
    expect(formatWeeksLeft(1)).toBe('1 week');
    expect(formatWeeksLeft(3.5)).toBe('3.5 weeks');
  });
});

describe('formatShortDate', () => {
  it('formats without shifting the day', () => {
    expect(formatShortDate('2026-12-03')).toBe('Dec 3');
    expect(formatShortDate(null)).toBe('—');
  });
});

describe('barHeights', () => {
  it('scales to the busiest week', () => {
    const week = (units: number) => ({ week_start: '2026-11-02', units, usable: true, excluded_reason: '' });
    expect(barHeights([week(5), week(10), week(0)])).toEqual([50, 100, 0]);
    expect(barHeights([week(0), week(0)])).toEqual([0, 0]);
  });
});

describe('forecastErrorMessage', () => {
  it("shows the server's validation message", () => {
    const error = { message: 'Request failed', response: { data: { history_weeks: ['Ensure this value is greater than or equal to 4.'] } } };
    expect(forecastErrorMessage(error)).toBe('Ensure this value is greater than or equal to 4.');
  });
});
