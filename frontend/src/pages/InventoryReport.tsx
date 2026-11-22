/**
 * Inventory Report (Issue #143)
 *
 * Staff report of what went out over a date range: items ordered, order
 * cost by program, and distinct participants per week, with a CSV download
 * of the same numbers. Data comes from GET /api/v1/reports/inventory/.
 */
import { useCallback, useEffect, useState } from 'react';
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
  Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import apiClient from '../lib/api/apiClient';
import {
  DATE_RANGE_OPTIONS,
  DEFAULT_FILTERS,
  GROUPING_OPTIONS,
  buildReportParams,
  filenameFromDisposition,
  formatDate,
  formatMoney,
  reportErrorMessage,
  type DateRangeChoice,
  type Grouping,
  type InventoryReport as InventoryReportData,
  type InventoryReportFilters,
} from '../lib/inventoryReport';

const REPORT_URL = '/reports/inventory/';

const Section = ({ title, subtitle, children }: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) => (
  <Card sx={{ mb: 3 }}>
    <CardContent>
      <Typography variant="h6">{title}</Typography>
      {subtitle && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {subtitle}
        </Typography>
      )}
      {children}
    </CardContent>
  </Card>
);

const EmptyRow = ({ colSpan, text }: { colSpan: number; text: string }) => (
  <TableRow>
    <TableCell colSpan={colSpan} align="center" sx={{ color: 'text.secondary', fontStyle: 'italic' }}>
      {text}
    </TableCell>
  </TableRow>
);

export const InventoryReport = () => {
  const notify = useNotify();
  const [filters, setFilters] = useState<InventoryReportFilters>(DEFAULT_FILTERS);
  const [report, setReport] = useState<InventoryReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: programs = [] } = useGetList('programs', {
    pagination: { page: 1, perPage: 200 },
    sort: { field: 'name', order: 'ASC' },
  });

  const runReport = useCallback(async (current: InventoryReportFilters) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(REPORT_URL, { params: buildReportParams(current) });
      setReport(response.data);
    } catch (err) {
      setError(reportErrorMessage(err));
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Show the default (last 6 months) as soon as the page opens.
  useEffect(() => {
    runReport(DEFAULT_FILTERS);
  }, [runReport]);

  const downloadCsv = async () => {
    setDownloading(true);
    try {
      const response = await apiClient.get(REPORT_URL, {
        params: { ...buildReportParams(filters), export: 'csv' },
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = filenameFromDisposition(response.headers['content-disposition']);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      notify(reportErrorMessage(err), { type: 'error' });
    } finally {
      setDownloading(false);
    }
  };

  const update = <K extends keyof InventoryReportFilters>(key: K, value: InventoryReportFilters[K]) =>
    setFilters((prev) => ({ ...prev, [key]: value }));

  const grouped = report !== null && report.grouping !== 'range';
  const partialWeeks = report?.participants_per_week.filter((w) => w.is_partial).length ?? 0;

  return (
    <Box sx={{ p: 2 }}>
      <Title title="Inventory Report" />

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'center' }} flexWrap="wrap" useFlexGap>
            <TextField
              select
              label="Date range"
              value={filters.date_range}
              onChange={(e) => update('date_range', e.target.value as DateRangeChoice)}
              sx={{ minWidth: 180 }}
              size="small"
            >
              {DATE_RANGE_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
              ))}
            </TextField>
            {filters.date_range === 'custom' && (
              <>
                <TextField
                  type="date"
                  label="Start date"
                  value={filters.start_date}
                  onChange={(e) => update('start_date', e.target.value)}
                  size="small"
                  slotProps={{ inputLabel: { shrink: true } }}
                />
                <TextField
                  type="date"
                  label="End date"
                  value={filters.end_date}
                  onChange={(e) => update('end_date', e.target.value)}
                  size="small"
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </>
            )}
            <TextField
              select
              label="Program"
              value={filters.program}
              onChange={(e) => update('program', e.target.value)}
              sx={{ minWidth: 180 }}
              size="small"
            >
              <MenuItem value="">All programs</MenuItem>
              {programs.map((p) => (
                <MenuItem key={p.id} value={String(p.id)}>{p.name}</MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Group results"
              value={filters.grouping}
              onChange={(e) => update('grouping', e.target.value as Grouping)}
              sx={{ minWidth: 160 }}
              size="small"
            >
              {GROUPING_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
              ))}
            </TextField>
            <Button
              variant="contained"
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
              onClick={() => runReport(filters)}
              disabled={loading}
            >
              Run report
            </Button>
            <Button
              variant="outlined"
              startIcon={downloading ? <CircularProgress size={16} /> : <DownloadIcon />}
              onClick={downloadCsv}
              disabled={downloading || loading}
            >
              Download CSV
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {report && (
        <>
          <Alert severity="info" sx={{ mb: 3 }}>
            <strong>{formatDate(report.start_date)} – {formatDate(report.end_date)}</strong>
            {report.program_name ? ` · ${report.program_name}` : ' · All programs'}
            . Counts confirmed, packing and completed orders by the date they were placed.
            Program is each participant&apos;s current program.
          </Alert>

          <Section title="Items ordered">
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Product</TableCell>
                    <TableCell>Category</TableCell>
                    <TableCell>Subcategory</TableCell>
                    {grouped && <TableCell>Period</TableCell>}
                    <TableCell align="right">Quantity</TableCell>
                    <TableCell align="right">Total cost</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.items.length === 0 && (
                    <EmptyRow colSpan={grouped ? 6 : 5} text="No orders in this range." />
                  )}
                  {report.items.map((row) => (
                    <TableRow key={`${row.period_key}-${row.product_name}`}>
                      <TableCell>{row.product_name}</TableCell>
                      <TableCell>{row.category}</TableCell>
                      <TableCell>{row.subcategory}</TableCell>
                      {grouped && <TableCell>{row.period_label}</TableCell>}
                      <TableCell align="right">{row.quantity}</TableCell>
                      <TableCell align="right">{formatMoney(row.total_cost)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Section>

          <Section title="Order cost by program">
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Program</TableCell>
                    {grouped && <TableCell>Period</TableCell>}
                    <TableCell align="right">Total cost</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.program_costs.length === 0 && (
                    <EmptyRow colSpan={grouped ? 3 : 2} text="No orders in this range." />
                  )}
                  {report.program_costs.map((row) => (
                    <TableRow key={`${row.period_key}-${row.program_name}`}>
                      <TableCell>{row.program_name || '(no program)'}</TableCell>
                      {grouped && <TableCell>{row.period_label}</TableCell>}
                      <TableCell align="right">{formatMoney(row.total_cost)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow>
                    <TableCell sx={{ fontWeight: 'bold' }}>Grand total</TableCell>
                    {grouped && <TableCell />}
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                      {formatMoney(report.grand_total)}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          </Section>

          <Section
            title="Participants per week"
            subtitle={
              'Distinct participants with at least one order. Weeks start Monday.' +
              (partialWeeks
                ? ' Weeks marked partial are cut short by the date range, so their counts cover fewer days.'
                : '')
            }
          >
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Week</TableCell>
                    <TableCell align="right">Participants</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.participants_per_week.map((row) => (
                    <TableRow key={row.week_start}>
                      <TableCell>
                        {formatDate(row.week_start)} – {formatDate(row.week_end)}
                        {row.is_partial && (
                          <Chip
                            size="small"
                            color="warning"
                            variant="outlined"
                            label={`partial: ${formatDate(row.counted_from)} – ${formatDate(row.counted_to)} only`}
                            sx={{ ml: 1 }}
                          />
                        )}
                      </TableCell>
                      <TableCell align="right">{row.participant_count}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Section>
        </>
      )}
    </Box>
  );
};

export default InventoryReport;
