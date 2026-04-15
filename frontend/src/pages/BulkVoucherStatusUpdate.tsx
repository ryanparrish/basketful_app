/**
 * Bulk Voucher Status Update Page - Two-Step Flow
 *
 * Step 1: Filter vouchers + select which ones to update
 * Step 2: Choose target state and confirm
 */
import { useState } from 'react';
import {
  Title,
  useNotify,
  useRedirect,
  useGetList,
  Loading,
} from 'react-admin';
import apiClient from '../lib/api/apiClient.ts';
import {
  Card,
  CardContent,
  CardHeader,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Checkbox,
  Alert,
  Box,
  Chip,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  CircularProgress,
  Typography,
  Paper,
  Divider,
} from '@mui/material';

// ─── Types ────────────────────────────────────────────────────────────────────

interface VoucherRow {
  id: number;
  participant_name: string;
  voucher_type: 'grocery' | 'life';
  state: 'pending' | 'applied' | 'consumed' | 'expired';
  voucher_amnt: number;
  active: boolean;
  created_at: string;
}

interface Program {
  id: number;
  name: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATE_CHOICES = [
  { id: 'pending', name: 'Pending' },
  { id: 'applied', name: 'Applied' },
  { id: 'consumed', name: 'Consumed' },
  { id: 'expired', name: 'Expired' },
];

/** Which target states are valid for a given current state. */
const ALLOWED_TRANSITIONS: Record<string, string[]> = {
  pending: ['applied', 'expired'],
  applied: ['expired'],
};

const TARGET_STATE_CHOICES = [
  { id: 'applied', name: 'Applied' },
  { id: 'expired', name: 'Expired' },
];

const STATE_COLORS: Record<string, string> = {
  pending: '#FFA726',
  applied: '#66BB6A',
  consumed: '#9E9E9E',
  expired: '#EF5350',
};

const StateChip = ({ state }: { state: string }) => (
  <Chip
    label={state.toUpperCase()}
    size="small"
    sx={{
      backgroundColor: STATE_COLORS[state] ?? '#9E9E9E',
      color: 'white',
      fontWeight: 600,
      fontSize: '0.7rem',
    }}
  />
);

// ─── Component ────────────────────────────────────────────────────────────────

export const BulkVoucherStatusUpdate = () => {
  const notify = useNotify();
  const redirect = useRedirect();

  // ── Step ──────────────────────────────────────────────────────────────────
  const [step, setStep] = useState<1 | 2>(1);

  // ── Step 1 filters ────────────────────────────────────────────────────────
  const [filterState, setFilterState] = useState<string>('pending');
  const [filterType, setFilterType] = useState<string>('');
  const [filterProgram, setFilterProgram] = useState<number | ''>('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  // ── Voucher list + selection ───────────────────────────────────────────────
  const [vouchers, setVouchers] = useState<VoucherRow[]>([]);
  const [loadingVouchers, setLoadingVouchers] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  // ── Step 2 ────────────────────────────────────────────────────────────────
  const [targetState, setTargetState] = useState<string>('applied');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<{ updated_count: number } | null>(null);

  // ── Programs (for filter dropdown) ───────────────────────────────────────
  const { data: programs, isPending: programsLoading } = useGetList<Program>('programs', {
    pagination: { page: 1, perPage: 100 },
    sort: { field: 'name', order: 'ASC' },
  });

  // ─── Step 1: load matching vouchers ────────────────────────────────────────
  const handleSearch = async () => {
    setLoadingVouchers(true);
    setVouchers([]);
    setSelectedIds([]);
    try {
      const params = new URLSearchParams();
      if (filterState) params.append('state', filterState);
      if (filterType) params.append('voucher_type', filterType);
      if (filterProgram) params.append('account__participant__program', String(filterProgram));
      if (filterDateFrom) params.append('created_at__gte', filterDateFrom);
      if (filterDateTo) params.append('created_at__lte', filterDateTo);
      params.append('page_size', '500');

      const response = await apiClient.get(`/vouchers/?${params.toString()}`);
      const rows: VoucherRow[] = response.data.results ?? response.data;
      setVouchers(rows);

      // Auto-select all that can transition to the current target
      const selectable = rows
        .filter(v => (ALLOWED_TRANSITIONS[v.state] ?? []).length > 0)
        .map(v => v.id);
      setSelectedIds(selectable);
    } catch (err) {
      notify(`Error loading vouchers: ${err}`, { type: 'error' });
    }
    setLoadingVouchers(false);
  };

  // ─── Selection helpers ─────────────────────────────────────────────────────
  const toggleId = (id: number) =>
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );

  const selectableVouchers = vouchers.filter(
    v => (ALLOWED_TRANSITIONS[v.state] ?? []).length > 0
  );

  const handleSelectAll = () => setSelectedIds(selectableVouchers.map(v => v.id));
  const handleDeselectAll = () => setSelectedIds([]);

  // ─── Step navigation ──────────────────────────────────────────────────────
  const handleNext = () => {
    if (selectedIds.length === 0) {
      notify('Select at least one voucher to continue', { type: 'warning' });
      return;
    }
    // Default target state to first allowed transition of selected vouchers
    const selectedVouchers = vouchers.filter(v => selectedIds.includes(v.id));
    const firstState = selectedVouchers[0]?.state;
    const defaultTarget = ALLOWED_TRANSITIONS[firstState]?.[0] ?? 'expired';
    setTargetState(defaultTarget);
    setStep(2);
  };

  const handleBack = () => {
    setStep(1);
    setResult(null);
  };

  // ─── Submit ───────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    setIsSubmitting(true);
    setResult(null);
    try {
      const response = await apiClient.post('/vouchers/bulk_update_status/', {
        voucher_ids: selectedIds,
        new_state: targetState,
      });
      setResult(response.data as { updated_count: number });
      notify(
        `Successfully updated ${response.data.updated_count} voucher(s) to "${targetState}"`,
        { type: 'success' }
      );
      setTimeout(() => redirect('/vouchers'), 2000);
    } catch (err) {
      notify(`Error updating vouchers: ${err}`, { type: 'error' });
    }
    setIsSubmitting(false);
  };

  // ─── Derived ──────────────────────────────────────────────────────────────
  const selectedVouchers = vouchers.filter(v => selectedIds.includes(v.id));
  const invalidForTarget = selectedVouchers.filter(
    v => !(ALLOWED_TRANSITIONS[v.state] ?? []).includes(targetState)
  );

  // Available target states = intersection of allowed transitions for all selected vouchers
  const availableTargets = TARGET_STATE_CHOICES.filter(choice =>
    selectedVouchers.every(v =>
      (ALLOWED_TRANSITIONS[v.state] ?? []).includes(choice.id)
    )
  );

  if (programsLoading) return <Loading />;

  return (
    <div>
      <Title title="Bulk Voucher Status Update" />

      <Card sx={{ maxWidth: 1000, m: 2 }}>
        <CardHeader
          title="Update Voucher Status in Bulk"
          subheader={`Step ${step} of 2: ${step === 1 ? 'Filter & Select Vouchers' : 'Choose New Status & Confirm'}`}
        />
        <CardContent>
          {/* ── STEP 1 ── */}
          {step === 1 && (
            <>
              {/* Filters */}
              <Typography variant="h6" gutterBottom>
                Filter Vouchers
              </Typography>

              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 3 }}>
                <FormControl sx={{ minWidth: 150 }}>
                  <InputLabel>Current State</InputLabel>
                  <Select
                    value={filterState}
                    onChange={e => setFilterState(e.target.value)}
                    label="Current State"
                  >
                    <MenuItem value="">Any</MenuItem>
                    {STATE_CHOICES.map(s => (
                      <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl sx={{ minWidth: 150 }}>
                  <InputLabel>Voucher Type</InputLabel>
                  <Select
                    value={filterType}
                    onChange={e => setFilterType(e.target.value)}
                    label="Voucher Type"
                  >
                    <MenuItem value="">Any</MenuItem>
                    <MenuItem value="grocery">Grocery</MenuItem>
                    <MenuItem value="life">Life Skills</MenuItem>
                  </Select>
                </FormControl>

                <FormControl sx={{ minWidth: 180 }}>
                  <InputLabel>Program</InputLabel>
                  <Select
                    value={filterProgram}
                    onChange={e => setFilterProgram(e.target.value as number | '')}
                    label="Program"
                  >
                    <MenuItem value="">Any</MenuItem>
                    {(programs ?? []).map(p => (
                      <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <TextField
                  label="Created From"
                  type="date"
                  value={filterDateFrom}
                  onChange={e => setFilterDateFrom(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ minWidth: 160 }}
                />

                <TextField
                  label="Created To"
                  type="date"
                  value={filterDateTo}
                  onChange={e => setFilterDateTo(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  sx={{ minWidth: 160 }}
                />
              </Box>

              <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
                <Button variant="contained" onClick={handleSearch} disabled={loadingVouchers}>
                  {loadingVouchers ? <CircularProgress size={20} sx={{ mr: 1 }} /> : null}
                  Search Vouchers
                </Button>
                <Button variant="outlined" onClick={() => redirect('/vouchers')}>
                  Cancel
                </Button>
              </Box>

              {/* Results */}
              {vouchers.length > 0 && (
                <>
                  <Divider sx={{ mb: 2 }} />
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="h6">
                      Results ({vouchers.length} found)
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      <Chip label={`${selectedIds.length} selected`} color="primary" />
                      <Button variant="outlined" size="small" onClick={handleSelectAll}>
                        Select All Eligible
                      </Button>
                      <Button variant="outlined" size="small" onClick={handleDeselectAll}>
                        Deselect All
                      </Button>
                    </Box>
                  </Box>

                  {vouchers.some(v => (ALLOWED_TRANSITIONS[v.state] ?? []).length === 0) && (
                    <Alert severity="info" sx={{ mb: 2 }}>
                      Some vouchers are in a terminal state (<strong>consumed</strong> or <strong>expired</strong>) and cannot be updated — they are shown greyed out.
                    </Alert>
                  )}

                  <Box sx={{ maxHeight: 450, overflow: 'auto', border: '1px solid #ddd', borderRadius: 1, mb: 3 }}>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell padding="checkbox" />
                          <TableCell>ID</TableCell>
                          <TableCell>Participant</TableCell>
                          <TableCell>Type</TableCell>
                          <TableCell>Current State</TableCell>
                          <TableCell>Amount</TableCell>
                          <TableCell>Created</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {vouchers.map(v => {
                          const canTransition = (ALLOWED_TRANSITIONS[v.state] ?? []).length > 0;
                          return (
                            <TableRow
                              key={v.id}
                              hover={canTransition}
                              onClick={() => canTransition && toggleId(v.id)}
                              sx={{
                                cursor: canTransition ? 'pointer' : 'default',
                                opacity: canTransition ? 1 : 0.45,
                              }}
                            >
                              <TableCell padding="checkbox">
                                <Checkbox
                                  checked={selectedIds.includes(v.id)}
                                  disabled={!canTransition}
                                />
                              </TableCell>
                              <TableCell>{v.id}</TableCell>
                              <TableCell>{v.participant_name}</TableCell>
                              <TableCell sx={{ textTransform: 'capitalize' }}>{v.voucher_type}</TableCell>
                              <TableCell><StateChip state={v.state} /></TableCell>
                              <TableCell>${Number(v.voucher_amnt).toFixed(2)}</TableCell>
                              <TableCell>{new Date(v.created_at).toLocaleDateString()}</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </Box>

                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <Button
                      variant="contained"
                      color="primary"
                      onClick={handleNext}
                      disabled={selectedIds.length === 0}
                    >
                      Next: Choose New Status
                    </Button>
                    <Button variant="outlined" onClick={() => redirect('/vouchers')}>
                      Cancel
                    </Button>
                  </Box>
                </>
              )}

              {vouchers.length === 0 && !loadingVouchers && (
                <Typography color="text.secondary" sx={{ mt: 2 }}>
                  Use the filters above and click <strong>Search Vouchers</strong> to load results.
                </Typography>
              )}
            </>
          )}

          {/* ── STEP 2 ── */}
          {step === 2 && (
            <>
              {/* Summary */}
              <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: '#f5f5f5' }}>
                <Typography variant="h6" gutterBottom>Selection Summary</Typography>
                <Divider sx={{ mb: 1.5 }} />
                <Typography variant="body2">
                  <strong>{selectedIds.length}</strong> voucher(s) selected
                </Typography>
                {Object.entries(
                  selectedVouchers.reduce<Record<string, number>>((acc, v) => {
                    acc[v.state] = (acc[v.state] ?? 0) + 1;
                    return acc;
                  }, {})
                ).map(([state, count]) => (
                  <Box key={state} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, mt: 0.5, mr: 1 }}>
                    <StateChip state={state} />
                    <Typography variant="body2">× {count}</Typography>
                  </Box>
                ))}
              </Paper>

              {/* Target state selector */}
              <FormControl fullWidth sx={{ mb: 3 }}>
                <InputLabel>New Status</InputLabel>
                <Select
                  value={targetState}
                  onChange={e => setTargetState(e.target.value)}
                  label="New Status"
                >
                  {availableTargets.length > 0 ? (
                    availableTargets.map(t => (
                      <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                    ))
                  ) : (
                    TARGET_STATE_CHOICES.map(t => (
                      <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                    ))
                  )}
                </Select>
              </FormControl>

              {/* Transition warnings */}
              {invalidForTarget.length > 0 && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                  <strong>{invalidForTarget.length}</strong> selected voucher(s) cannot be moved to
                  "{targetState}" from their current state and will be skipped:{' '}
                  {invalidForTarget.map(v => `#${v.id} (${v.state})`).join(', ')}
                </Alert>
              )}

              {targetState === 'expired' && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                  Expiring vouchers will also set them to <strong>inactive</strong>. This cannot be undone.
                </Alert>
              )}

              {/* Voucher preview table */}
              <Typography variant="subtitle1" gutterBottom>
                Vouchers to update ({selectedVouchers.filter(v => (ALLOWED_TRANSITIONS[v.state] ?? []).includes(targetState)).length} eligible):
              </Typography>
              <Box sx={{ maxHeight: 350, overflow: 'auto', border: '1px solid #ddd', borderRadius: 1, mb: 3 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>ID</TableCell>
                      <TableCell>Participant</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Current State</TableCell>
                      <TableCell>→ New State</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {selectedVouchers.map(v => {
                      const eligible = (ALLOWED_TRANSITIONS[v.state] ?? []).includes(targetState);
                      return (
                        <TableRow
                          key={v.id}
                          sx={{ opacity: eligible ? 1 : 0.45 }}
                        >
                          <TableCell>{v.id}</TableCell>
                          <TableCell>{v.participant_name}</TableCell>
                          <TableCell sx={{ textTransform: 'capitalize' }}>{v.voucher_type}</TableCell>
                          <TableCell><StateChip state={v.state} /></TableCell>
                          <TableCell>
                            {eligible ? (
                              <StateChip state={targetState} />
                            ) : (
                              <Chip label="SKIP" size="small" sx={{ backgroundColor: '#bdbdbd', color: 'white', fontWeight: 600 }} />
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </Box>

              {/* Result */}
              {result && (
                <Alert severity="success" sx={{ mb: 3 }}>
                  Successfully updated {result.updated_count} voucher(s) to "{targetState}".
                </Alert>
              )}

              {/* Actions */}
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleSubmit}
                  disabled={
                    isSubmitting ||
                    selectedVouchers.filter(v =>
                      (ALLOWED_TRANSITIONS[v.state] ?? []).includes(targetState)
                    ).length === 0
                  }
                >
                  {isSubmitting ? <CircularProgress size={24} /> : `Update ${selectedVouchers.filter(v => (ALLOWED_TRANSITIONS[v.state] ?? []).includes(targetState)).length} Voucher(s)`}
                </Button>
                <Button variant="outlined" onClick={handleBack} disabled={isSubmitting}>
                  Back
                </Button>
                <Button variant="outlined" onClick={() => redirect('/vouchers')} disabled={isSubmitting}>
                  Cancel
                </Button>
              </Box>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default BulkVoucherStatusUpdate;
