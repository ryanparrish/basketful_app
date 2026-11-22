/**
 * Stock forecast widgets (Issue #148): status chip, the products-list
 * "Weeks left" cell, and the product page's weekly usage panel.
 */
import { useEffect, useState } from 'react';
import { useRecordContext } from 'react-admin';
import { Link } from 'react-router-dom';
import { Box, Chip, CircularProgress, Stack, Tooltip, Typography } from '@mui/material';
import apiClient from '../lib/api/apiClient';
import {
  STATUS_META,
  barHeights,
  formatShortDate,
  formatWeeksLeft,
  type ForecastRow,
  type ForecastStatus,
} from '../lib/stockForecast';

export const StatusChip = ({ status }: { status: ForecastStatus }) => {
  const meta = STATUS_META[status];
  return (
    <Tooltip title={meta.description}>
      <Chip
        size="small"
        label={meta.label}
        color={meta.color}
        variant={status === 'ok' ? 'outlined' : 'filled'}
      />
    </Tooltip>
  );
};

/** Products list cell: "3.5 weeks" colored by forecast status. */
export const WeeksLeftCell = () => {
  const record = useRecordContext<{ forecast_status?: ForecastStatus | null; forecast_weeks_left?: number | null }>();
  if (!record?.forecast_status) return null;
  const status = record.forecast_status;
  if (status === 'insufficient_history') {
    return (
      <Typography variant="body2" color="text.secondary">
        —
      </Typography>
    );
  }
  const color = status === 'critical' ? 'error.main' : status === 'low' ? 'warning.main' : 'text.primary';
  return (
    <Tooltip title={STATUS_META[status].description}>
      <Typography variant="body2" sx={{ color, fontWeight: status === 'ok' ? 'normal' : 'bold' }}>
        {formatWeeksLeft(record.forecast_weeks_left ?? null)}
      </Typography>
    </Tooltip>
  );
};

/** Product page: weekly units for the forecast window plus the numbers. */
export const ProductUsagePanel = () => {
  const record = useRecordContext();
  const [row, setRow] = useState<ForecastRow | null>(null);
  const [loading, setLoading] = useState(true);
  const productId = record?.id;

  useEffect(() => {
    if (productId === undefined) return;
    let cancelled = false;
    setLoading(true);
    apiClient
      .get('/reports/stock-forecast/', { params: { product: productId } })
      .then((response) => {
        if (!cancelled) setRow(response.data.results[0] ?? null);
      })
      .catch(() => {
        if (!cancelled) setRow(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [productId]);

  if (loading) return <CircularProgress size={20} />;
  if (!row) return <Typography variant="body2">No forecast available.</Typography>;

  const heights = barHeights(row.history);
  return (
    <Box>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 1 }} flexWrap="wrap" useFlexGap>
        <StatusChip status={row.status} />
        <Typography variant="body2">
          Per week: <strong>{row.weekly_usage ?? '—'}</strong>
        </Typography>
        <Typography variant="body2">
          Available: <strong>{row.available}</strong>
          {row.pending_units ? ` (${row.pending_units} on pending orders)` : ''}
        </Typography>
        <Typography variant="body2">
          Weeks left: <strong>{formatWeeksLeft(row.weeks_left)}</strong>
        </Typography>
        <Typography variant="body2">
          Runs out: <strong>{formatShortDate(row.runout_date)}</strong>
        </Typography>
        <Typography variant="body2">
          Suggested reorder: <strong>{row.suggested_reorder ?? '—'}</strong>
        </Typography>
      </Stack>
      <Box
        aria-label="Weekly units ordered"
        sx={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: 64, mb: 0.5, maxWidth: 480 }}
      >
        {row.history.map((week, i) => (
          <Tooltip
            key={week.week_start}
            title={`Week of ${formatShortDate(week.week_start)}: ${week.units} ordered${
              week.usable ? '' : ` (left out: ${week.excluded_reason})`
            }`}
          >
            <Box
              sx={{
                flex: 1,
                height: `${Math.max(heights[i], 3)}%`,
                bgcolor: week.usable ? 'primary.main' : 'action.disabled',
                borderRadius: '2px 2px 0 0',
                backgroundImage: week.usable
                  ? 'none'
                  : 'repeating-linear-gradient(45deg, transparent, transparent 3px, rgba(255,255,255,0.5) 3px, rgba(255,255,255,0.5) 6px)',
              }}
            />
          </Tooltip>
        ))}
      </Box>
      <Typography variant="caption" color="text.secondary" component="div">
        {row.explanation} Grey bars are weeks left out of the average.{' '}
        <Link to="/reports/stock-forecast">Full forecast</Link>
      </Typography>
    </Box>
  );
};
