/**
 * CreateCombinedOrder — 4-step wizard (Configure → Preview → Creating → Success).
 * Mirrors CombinedOrderAdmin create/preview/confirm/success workflow from admin.py.
 */
import { useState } from 'react';
import { Title, useNotify, useGetList } from 'react-admin';
import {
  Stepper,
  Step,
  StepLabel,
  Button,
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Paper,
  TextField,
  MenuItem,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DownloadIcon from '@mui/icons-material/Download';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { API_URL } from '../utils/apiUrl';

const STEPS = ['Configure', 'Preview', 'Creating', 'Success'];

interface FormData {
  program_id: string;
  start_date: string;
  end_date: string;
}

interface SplitItem {
  packer_name: string;
  order_count: number;
  item_count: number;
  categories: string[] | string;
}

interface PreviewData {
  program: { id: number; name: string };
  effective_strategy: string;
  strategy_display: string;
  eligible_count: number;
  excluded_count: number;
  warnings: string[];
  errors: string[];
  preview_data: {
    order_count: number;
    total_items: number;
    total_value: string;
    category_totals: Record<string, number>;
    packer_count: number;
    split_preview: SplitItem[];
  };
  can_proceed: boolean;
  order_ids: number[];
}

interface PackingListSummary {
  id: number;
  packer_name: string;
}

interface CreatedOrder {
  id: number;
  name: string;
  packing_lists?: PackingListSummary[];
}

export const CreateCombinedOrder = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState<FormData>({
    program_id: '',
    start_date: '',
    end_date: '',
  });
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [createdOrder, setCreatedOrder] = useState<CreatedOrder | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const notify = useNotify();
  const navigate = useNavigate();

  const { data: programs } = useGetList<{ id: number; name: string }>('programs', {
    pagination: { page: 1, perPage: 200 },
    sort: { field: 'name', order: 'ASC' },
  });

  const authHeader = () => {
    const token = localStorage.getItem('accessToken');
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  };

  // ── Step 0 → 1: fetch preview ──────────────────────────────────────────────
  const handlePreview = async () => {
    if (!formData.program_id || !formData.start_date || !formData.end_date) {
      notify('Please fill in all required fields', { type: 'error' });
      return;
    }
    setIsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/combined-orders/preview/`, {
        method: 'POST',
        headers: authHeader(),
        body: JSON.stringify({
          program_id: parseInt(formData.program_id),
          start_date: formData.start_date,
          end_date: formData.end_date,
        }),
      });
      const data = await res.json();
      if (!res.ok) { notify(data.error || 'Preview failed', { type: 'error' }); return; }
      setPreview(data);
      setActiveStep(1);
    } catch {
      notify('Error fetching preview', { type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  // ── Step 1 → 2/3: create combined order ───────────────────────────────────
  const handleCreate = async () => {
    if (!preview) return;
    setActiveStep(2);
    setIsLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/combined-orders/create-with-packing/`, {
        method: 'POST',
        headers: authHeader(),
        body: JSON.stringify({
          program_id: preview.program.id,
          order_ids: preview.order_ids,
          strategy: preview.effective_strategy,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data.error || 'Creation failed';
        setCreateError(msg);
        notify(msg, { type: 'error' });
        setActiveStep(0);
        return;
      }
      setCreatedOrder(data);
      setActiveStep(3);
    } catch {
      notify('Error creating combined order', { type: 'error' });
      setActiveStep(1);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = async (url: string, filename: string) => {
    try {
      const token = localStorage.getItem('accessToken');
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = window.URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(a.href);
      document.body.removeChild(a);
    } catch {
      notify('Download failed', { type: 'error' });
    }
  };

  return (
    <div>
      <Title title="Create Combined Order" />
      <Card sx={{ m: 2 }}>
        <CardContent>
          <Alert severity="info" sx={{ mb: 3 }}>
            <strong>How to Create a Combined Order:</strong>
            <ol style={{ margin: '8px 0 0', paddingLeft: 20, lineHeight: 1.8 }}>
              <li><strong>Configure:</strong> Select program and date range.</li>
              <li><strong>Preview:</strong> Review eligible orders, totals, and packing split.</li>
              <li><strong>Create:</strong> Confirm to generate the combined order and packing lists.</li>
            </ol>
          </Alert>

          <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
            {STEPS.map((label) => (
              <Step key={label}><StepLabel>{label}</StepLabel></Step>
            ))}
          </Stepper>

          {/* ── Step 0: Configure ────────────────────────────────────────── */}
          {activeStep === 0 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Step 1: Select Program and Time Frame
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 520 }}>
                <TextField
                  select
                  label="Program *"
                  value={formData.program_id}
                  onChange={(e) => {
                    const selectedId = e.target.value;
                    setCreateError(null);
                    setFormData((p) => ({ ...p, program_id: selectedId }));
                  }}
                  fullWidth
                >
                  <MenuItem value="">-- Select Program --</MenuItem>
                  {(programs || []).map((prog) => (
                    <MenuItem
                      key={prog.id}
                      value={String(prog.id)}
                    >
                      {prog.name}
                    </MenuItem>
                  ))}
                </TextField>

                <TextField
                  label="Start Date *"
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData((p) => ({ ...p, start_date: e.target.value }))}
                  InputLabelProps={{ shrink: true }}
                  fullWidth
                />
                <TextField
                  label="End Date *"
                  type="date"
                  value={formData.end_date}
                  onChange={(e) => setFormData((p) => ({ ...p, end_date: e.target.value }))}
                  InputLabelProps={{ shrink: true }}
                  fullWidth
                />

                <Box>
                  {createError && (
                    <Alert severity="error" sx={{ mb: 2 }} onClose={() => setCreateError(null)}>
                      {createError}
                    </Alert>
                  )}
                  <Button
                    variant="contained"
                    onClick={handlePreview}
                    disabled={
                      isLoading ||
                      !formData.program_id ||
                      !formData.start_date ||
                      !formData.end_date
                    }
                    startIcon={isLoading ? <CircularProgress size={16} /> : undefined}
                  >
                    {isLoading ? 'Loading Preview…' : 'Preview Orders →'}
                  </Button>
                </Box>
              </Box>
            </Box>
          )}

          {/* ── Step 1: Preview ──────────────────────────────────────────── */}
          {activeStep === 1 && preview && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Step 2: Preview — {preview.eligible_count} eligible orders for{' '}
                <strong>{preview.program.name}</strong>
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Date Range: {formData.start_date} → {formData.end_date}&nbsp;|&nbsp;
                Split Strategy: <strong>{preview.strategy_display}</strong>
              </Typography>

              {/* Errors */}
              {preview.errors.length > 0 && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  <strong>❌ Errors (Cannot Proceed):</strong>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                    {preview.errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </Alert>
              )}

              {/* Warnings */}
              {preview.warnings.length > 0 && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  <strong>⚠️ Warnings:</strong>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                    {preview.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </Alert>
              )}

              {preview.can_proceed && (
                <>
                  {/* Totals */}
                  <Paper sx={{ p: 2, mb: 2 }}>
                    <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                      Order Totals
                    </Typography>
                    <Table size="small">
                      <TableBody>
                        <TableRow>
                          <TableCell><strong>Total Orders</strong></TableCell>
                          <TableCell>{preview.preview_data.order_count}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell><strong>Total Items</strong></TableCell>
                          <TableCell>{preview.preview_data.total_items}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell><strong>Total Value</strong></TableCell>
                          <TableCell>
                            ${parseFloat(preview.preview_data.total_value || '0').toFixed(2)}
                          </TableCell>
                        </TableRow>
                        {preview.excluded_count > 0 && (
                          <TableRow>
                            <TableCell><strong>Excluded (Already Combined)</strong></TableCell>
                            <TableCell>{preview.excluded_count}</TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </Paper>

                  {/* Items by Category */}
                  {Object.keys(preview.preview_data.category_totals || {}).length > 0 && (
                    <Paper sx={{ p: 2, mb: 2 }}>
                      <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                        Items by Category
                      </Typography>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell><strong>Category</strong></TableCell>
                            <TableCell><strong>Quantity</strong></TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {Object.entries(preview.preview_data.category_totals).map(
                            ([cat, qty]) => (
                              <TableRow key={cat}>
                                <TableCell>{cat}</TableCell>
                                <TableCell>{qty as number}</TableCell>
                              </TableRow>
                            )
                          )}
                        </TableBody>
                      </Table>
                    </Paper>
                  )}

                  {/* Packing Split Preview */}
                  {preview.preview_data.packer_count > 1 &&
                    preview.preview_data.split_preview?.length > 0 && (
                      <Paper sx={{ p: 2, mb: 2 }}>
                        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                          📋 Packing Split Preview ({preview.preview_data.packer_count} packers)
                        </Typography>
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell><strong>Packer</strong></TableCell>
                              <TableCell><strong>Orders</strong></TableCell>
                              <TableCell><strong>Items</strong></TableCell>
                              <TableCell><strong>Categories</strong></TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {preview.preview_data.split_preview.map((split, i) => (
                              <TableRow key={i}>
                                <TableCell><strong>{split.packer_name}</strong></TableCell>
                                <TableCell>{split.order_count}</TableCell>
                                <TableCell>{split.item_count}</TableCell>
                                <TableCell>
                                  {Array.isArray(split.categories)
                                    ? split.categories.join(', ') || 'All categories'
                                    : split.categories}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </Paper>
                    )}
                </>
              )}

              <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={<ArrowBackIcon />}
                  onClick={() => setActiveStep(0)}
                >
                  Back
                </Button>
                {preview.can_proceed && (
                  <Button variant="contained" color="primary" onClick={handleCreate}>
                    ✓ Create Combined Order
                  </Button>
                )}
              </Box>
            </Box>
          )}

          {/* ── Step 2: Creating ─────────────────────────────────────────── */}
          {activeStep === 2 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 6, gap: 2 }}>
              <CircularProgress size={60} />
              <Typography variant="h6">Creating Combined Order…</Typography>
              <Typography variant="body2" color="text.secondary">
                Generating packing lists and assignments. Please wait.
              </Typography>
            </Box>
          )}

          {/* ── Step 3: Success ──────────────────────────────────────────── */}
          {activeStep === 3 && createdOrder && (
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <CheckCircleIcon color="success" sx={{ fontSize: 40 }} />
                <Typography variant="h5">Combined Order Created!</Typography>
              </Box>
              <Alert severity="success" sx={{ mb: 3 }}>
                Successfully combined {preview?.eligible_count || 0} orders.
              </Alert>

              <Paper sx={{ p: 2, mb: 3 }}>
                <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                  Downloads
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  <Button
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={() =>
                      handleDownload(
                        `${API_URL}/api/v1/combined-orders/${createdOrder.id}/download-primary-pdf/`,
                        `primary_order_${createdOrder.id}.pdf`
                      )
                    }
                  >
                    Primary Order PDF
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={() =>
                      handleDownload(
                        `${API_URL}/api/v1/combined-orders/${createdOrder.id}/download-all-packing-lists/`,
                        `combined_order_${createdOrder.id}_all_lists.zip`
                      )
                    }
                  >
                    All Packing Lists (ZIP)
                  </Button>
                </Box>

                {(createdOrder.packing_lists || []).length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Individual Packing Lists:
                    </Typography>
                    {(createdOrder.packing_lists || []).map((pl) => (
                      <Button
                        key={pl.id}
                        size="small"
                        startIcon={<DownloadIcon />}
                        onClick={() =>
                          handleDownload(
                            `${API_URL}/api/v1/packing-lists/${pl.id}/download-pdf/`,
                            `packing_list_${pl.packer_name.replace(/\s+/g, '_')}_${createdOrder.id}.pdf`
                          )
                        }
                        sx={{ mr: 1, mb: 1 }}
                      >
                        {pl.packer_name}
                      </Button>
                    ))}
                  </Box>
                )}
              </Paper>

              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  onClick={() => navigate(`/combined-orders/${createdOrder.id}/show`)}
                >
                  View Combined Order
                </Button>
                <Button variant="outlined" onClick={() => navigate('/combined-orders')}>
                  Back to List
                </Button>
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default CreateCombinedOrder;
