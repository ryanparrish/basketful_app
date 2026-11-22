/**
 * Stock Forecast (Issue #148)
 *
 * Pantry-wide: how fast each product goes out, how long the stock on hand
 * lasts (after pending orders), roughly when it runs out, and how much to
 * reorder, with a reorder-list CSV for the Feeding America order.
 * Data comes from GET /api/v1/reports/stock-forecast/.
 */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Title, useGetList, useNotify } from 'react-admin';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { StatusChip } from '../components/StockForecastWidgets';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import apiClient from '../lib/api/apiClient';
import {
  DEFAULT_FORECAST_SETTINGS,
  STATUS_META,
  STATUS_OPTIONS,
  buildForecastParams,
  forecastErrorMessage,
  formatShortDate,
  formatWeeksLeft,
  type ForecastResponse,
  type ForecastSettings,
  type ForecastStatus,
} from '../lib/stockForecast';

const FORECAST_URL = '/reports/stock-forecast/';

export const StockForecast = () => {
  const notify = useNotify();
  const [settings, setSettings] = useState<ForecastSettings>(DEFAULT_FORECAST_SETTINGS);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: categories = [] } = useGetList('categories', {
    pagination: { page: 1, perPage: 200 },
    sort: { field: 'name', order: 'ASC' },
  });

  const load = useCallback(async (current: ForecastSettings) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(FORECAST_URL, { params: buildForecastParams(current) });
      setForecast(response.data);
    } catch (err) {
      setError(forecastErrorMessage(err));
      setForecast(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(DEFAULT_FORECAST_SETTINGS);
  }, [load]);

  const downloadCsv = async () => {
    setDownloading(true);
    try {
      const response = await apiClient.get(FORECAST_URL, {
        params: { ...buildForecastParams(settings), export: 'csv' },
        responseType: 'blob',
      });
      const disposition: string | undefined = response.headers['content-disposition'];
      const filename = disposition?.match(/filename="?([^";]+)"?/i)?.[1] ?? 'reorder_list.csv';
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      notify(forecastErrorMessage(err), { type: 'error' });
    } finally {
      setDownloading(false);
    }
  };

  const update = <K extends keyof ForecastSettings>(key: K, value: ForecastSettings[K]) =>
    setSettings((prev) => ({ ...prev, [key]: value }));

  const counts = forecast?.results.reduce<Record<string, number>>((acc, row) => {
    acc[row.status] = (acc[row.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <Box sx={{ p: 2 }}>
      <Title title="Stock Forecast" />

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'center' }} flexWrap="wrap" useFlexGap>
            <TextField
              type="number"
              size="small"
              label="Usage from last (weeks)"
              value={settings.history_weeks}
              onChange={(e) => update('history_weeks', Number(e.target.value))}
              slotProps={{ htmlInput: { min: 4, max: 52 } }}
              sx={{ width: 190 }}
            />
            <TextField
              type="number"
              size="small"
              label="Cover (weeks)"
              value={settings.cover_weeks}
              onChange={(e) => update('cover_weeks', Number(e.target.value))}
              slotProps={{ htmlInput: { min: 1, max: 26 } }}
              sx={{ width: 140 }}
            />
            <TextField
              type="number"
              size="small"
              label="Safety (weeks)"
              value={settings.safety_weeks}
              onChange={(e) => update('safety_weeks', Number(e.target.value))}
              slotProps={{ htmlInput: { min: 0, max: 8 } }}
              sx={{ width: 140 }}
            />
            <TextField
              select
              size="small"
              label="Category"
              value={settings.category}
              onChange={(e) => update('category', e.target.value)}
              sx={{ minWidth: 170 }}
            >
              <MenuItem value="">All categories</MenuItem>
              {categories.map((c) => (
                <MenuItem key={c.id} value={String(c.id)}>{c.name}</MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Status"
              value={settings.status}
              onChange={(e) => update('status', e.target.value as ForecastSettings['status'])}
              sx={{ minWidth: 170 }}
            >
              {STATUS_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
              ))}
            </TextField>
            <Button
              variant="contained"
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}
              onClick={() => load(settings)}
              disabled={loading}
            >
              Update
            </Button>
            <Button
              variant="outlined"
              startIcon={downloading ? <CircularProgress size={16} /> : <DownloadIcon />}
              onClick={downloadCsv}
              disabled={downloading || loading}
            >
              Reorder list (CSV)
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {forecast && (
        <>
          <Alert severity="info" sx={{ mb: 2 }}>
            Weekly usage is a recent-weighted average of confirmed, packing and completed orders over the
            last {forecast.history_weeks} complete weeks, leaving out weeks a product couldn&apos;t be ordered.
            Available = on hand − pending orders. Suggested reorder covers {forecast.cover_weeks} week(s) plus{' '}
            {forecast.safety_weeks} safety week(s).
          </Alert>

          <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
            {(['critical', 'low', 'ok', 'insufficient_history'] as ForecastStatus[]).map((s) => (
              <Chip
                key={s}
                label={`${STATUS_META[s].label}: ${counts?.[s] ?? 0}`}
                color={STATUS_META[s].color}
                variant={settings.status === s ? 'filled' : 'outlined'}
                onClick={() => {
                  const next = { ...settings, status: settings.status === s ? '' : s } as ForecastSettings;
                  setSettings(next);
                  load(next);
                }}
              />
            ))}
          </Stack>

          <Card>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Status</TableCell>
                    <TableCell>Product</TableCell>
                    <TableCell>Category</TableCell>
                    <TableCell align="right">On hand</TableCell>
                    <TableCell align="right">Pending</TableCell>
                    <TableCell align="right">Available</TableCell>
                    <TableCell align="right">Per week</TableCell>
                    <TableCell align="right">Weeks left</TableCell>
                    <TableCell>Runs out</TableCell>
                    <TableCell align="right">Suggested reorder</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {forecast.results.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={10} align="center" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
                        No products match.
                      </TableCell>
                    </TableRow>
                  )}
                  {forecast.results.map((row) => (
                    <TableRow key={row.product_id} hover>
                      <TableCell><StatusChip status={row.status} /></TableCell>
                      <TableCell>
                        <Tooltip title={row.explanation}>
                          <Link to={`/products/${row.product_id}/show`}>{row.product_name}</Link>
                        </Tooltip>
                        {!row.active && (
                          <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                            (inactive)
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>{row.category}</TableCell>
                      <TableCell align="right">{row.quantity_in_stock}</TableCell>
                      <TableCell align="right">{row.pending_units || ''}</TableCell>
                      <TableCell align="right">{row.available}</TableCell>
                      <TableCell align="right">{row.weekly_usage ?? '—'}</TableCell>
                      <TableCell align="right">{formatWeeksLeft(row.weeks_left)}</TableCell>
                      <TableCell>{formatShortDate(row.runout_date)}</TableCell>
                      <TableCell align="right" sx={{ fontWeight: row.suggested_reorder ? 'bold' : 'normal' }}>
                        {row.suggested_reorder ?? '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>
        </>
      )}
    </Box>
  );
};

export default StockForecast;
