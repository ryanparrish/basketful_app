/**
 * Settings Page
 * 
 * Manage system-wide settings including order window, email, and branding.
 */
import { useState, useEffect } from 'react';
import {
  Title,
  useDataProvider,
  useNotify,
  Loading,
} from 'react-admin';
import {
  Card,
  CardContent,
  CardHeader,
  Button,
  TextField,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
  Box,
  Alert,
  AlertTitle,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  CircularProgress,
  Divider,
  Typography,
} from '@mui/material';
import { API_URL } from '../utils/apiUrl';
import { useDebounce } from '../utils/useDebounce';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => (
  <div hidden={value !== index} style={{ padding: '20px 0' }}>
    {value === index && children}
  </div>
);

interface OrderWindowSettings {
  id: number;
  hours_before_class: number;
  hours_before_close: number;
  enabled: boolean;
  is_open: boolean;
  next_opens_at: string | null;
  next_closes_at: string | null;
}

interface EmailSettings {
  id: number;
  from_email_default: string;
  reply_to_default: string;
  effective_from_email: string;
}

interface BrandingSettings {
  id: number;
  organization_name: string;
  logo: string | null;
}

interface VoucherSettings {
  id: number;
  adult_amount: number;
  child_amount: number;
  infant_modifier: number;
  active: boolean;
}

interface ProgramPause {
  id: number;
  reason: string | null;
  pause_start: string;
  pause_end: string;
  multiplier: number;
  is_active: boolean;
  archived: boolean;
  archived_at: string | null;
}

interface PauseFormData {
  id: number | null;
  reason: string;
  pause_start: string;
  pause_end: string;
}

export const Settings = () => {
  const dataProvider = useDataProvider();
  const notify = useNotify();
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Settings state
  const [orderWindow, setOrderWindow] = useState<OrderWindowSettings | null>(null);
  const [email, setEmail] = useState<EmailSettings | null>(null);
  const [branding, setBranding] = useState<BrandingSettings | null>(null);
  const [voucher, setVoucher] = useState<VoucherSettings | null>(null);

  // Program Pauses state
  const [pauses, setPauses] = useState<ProgramPause[]>([]);
  const [activePause, setActivePause] = useState<ProgramPause | null>(null);
  const [pauseForm, setPauseForm] = useState<PauseFormData>({ id: null, reason: '', pause_start: '', pause_end: '' });
  const [pauseModalOpen, setPauseModalOpen] = useState(false);
  const [pauseFormError, setPauseFormError] = useState<string | null>(null);
  const [overlapError, setOverlapError] = useState<string | null>(null);
  const [pauseSaving, setPauseSaving] = useState(false);
  const [pausesLoading, setPausesLoading] = useState(false);

  // Debounced pause form dates for real-time overlap check
  const debouncedPauseStart = useDebounce(pauseForm.pause_start, 500);
  const debouncedPauseEnd = useDebounce(pauseForm.pause_end, 500);

  // Fetch all settings
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [owResponse, emailResponse, brandingResponse, voucherResponse] =
          await Promise.all([
            dataProvider.getOne('settings/order-window-settings', { id: 'current' }),
            dataProvider.getOne('settings/email-settings', { id: 'current' }),
            dataProvider.getOne('settings/branding-settings', { id: 'current' }),
            dataProvider.getList('voucher-settings', {
              pagination: { page: 1, perPage: 1 },
              filter: { active: true },
              sort: { field: 'id', order: 'DESC' },
            }),
          ]);

        setOrderWindow(owResponse.data as OrderWindowSettings);
        setEmail(emailResponse.data as EmailSettings);
        setBranding(brandingResponse.data as BrandingSettings);
        if (voucherResponse.data.length > 0) {
          setVoucher(voucherResponse.data[0] as VoucherSettings);
        }
      } catch {
        notify('Error loading settings', { type: 'error' });
      }
      setLoading(false);
    };

    fetchSettings();
  }, [dataProvider, notify]);

  // Save Order Window Settings
  const saveOrderWindow = async () => {
    if (!orderWindow) return;
    setSaving(true);
    try {
      await dataProvider.update('settings/order-window-settings', {
        id: 'current',
        data: orderWindow,
        previousData: orderWindow,
      });
      notify('Order window settings saved', { type: 'success' });
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  // Save Email Settings
  const saveEmail = async () => {
    if (!email) return;
    setSaving(true);
    try {
      await dataProvider.update('settings/email-settings', {
        id: 'current',
        data: email,
        previousData: email,
      });
      notify('Email settings saved', { type: 'success' });
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  // Save Branding Settings
  const saveBranding = async () => {
    if (!branding) return;
    setSaving(true);
    try {
      await dataProvider.update('settings/branding-settings', {
        id: 'current',
        data: branding,
        previousData: branding,
      });
      notify('Branding settings saved', { type: 'success' });
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  // Save Voucher Settings
  const saveVoucher = async () => {
    if (!voucher) return;
    setSaving(true);
    try {
      await dataProvider.update('voucher-settings', {
        id: voucher.id,
        data: voucher,
        previousData: voucher,
      });
      notify('Voucher settings saved', { type: 'success' });
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
  };

  // Fetch all program pauses + active pause
  const fetchPauses = () => {
    setPausesLoading(true);
    const token = localStorage.getItem('accessToken');
    Promise.all([
      fetch(`${API_URL}/api/v1/program-pauses/?ordering=-pause_start`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.ok ? r.json() : { results: [] }),
      fetch(`${API_URL}/api/v1/program-pauses/active/`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.ok ? r.json() : []),
    ])
      .then(([allData, activeData]) => {
        setPauses(allData.results || []);
        setActivePause(activeData.length > 0 ? activeData[0] : null);
        setPausesLoading(false);
      })
      .catch(() => setPausesLoading(false));
  };

  useEffect(() => {
    fetchPauses();
   
  }, []);

  // Real-time overlap check — fires 500ms after dates change
  useEffect(() => {
    if (!debouncedPauseStart || !debouncedPauseEnd) {
      setOverlapError(null);
      return;
    }
    const token = localStorage.getItem('accessToken');
    const params = new URLSearchParams({
      pause_start: debouncedPauseStart,
      pause_end: debouncedPauseEnd,
    });
    if (pauseForm.id) params.append('exclude_id', String(pauseForm.id));
    fetch(`${API_URL}/api/v1/program-pauses/check_overlap/?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.overlaps) {
          const c = data.conflicting;
          setOverlapError(
            `Overlaps with: "${c.reason || 'Unnamed'}" (${new Date(c.pause_start).toLocaleDateString()} – ${new Date(c.pause_end).toLocaleDateString()})`
          );
        } else {
          setOverlapError(null);
        }
      })
      .catch(() => setOverlapError(null));
  }, [debouncedPauseStart, debouncedPauseEnd, pauseForm.id]);

  const validatePauseForm = (): string | null => {
    const now = new Date();
    const start = new Date(pauseForm.pause_start);
    const end = new Date(pauseForm.pause_end);
    if (!pauseForm.pause_start || !pauseForm.pause_end) return 'Start and end dates are required.';
    if (isNaN(start.getTime()) || isNaN(end.getTime())) return 'Invalid date format.';
    if (end <= start) return 'End date must be after start date.';
    const minStart = new Date(now.getTime() + 11 * 24 * 60 * 60 * 1000);
    if (start < minStart) return 'Pause must start at least 11 days from today.';
    const durationDays = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24);
    if (durationDays > 14) return 'Pause cannot be longer than 14 days.';
    return null;
  };

  const openCreateModal = () => {
    setPauseForm({ id: null, reason: '', pause_start: '', pause_end: '' });
    setPauseFormError(null);
    setOverlapError(null);
    setPauseModalOpen(true);
  };

  const openEditModal = (pause: ProgramPause) => {
    const toLocal = (iso: string) => iso ? iso.slice(0, 16) : '';
    setPauseForm({
      id: pause.id,
      reason: pause.reason || '',
      pause_start: toLocal(pause.pause_start),
      pause_end: toLocal(pause.pause_end),
    });
    setPauseFormError(null);
    setOverlapError(null);
    setPauseModalOpen(true);
  };

  const savePause = async () => {
    const err = validatePauseForm();
    if (err) { setPauseFormError(err); return; }
    if (overlapError) { setPauseFormError('Resolve the overlap conflict before saving.'); return; }
    setPauseSaving(true);
    const token = localStorage.getItem('accessToken');
    const url = pauseForm.id
      ? `${API_URL}/api/v1/program-pauses/${pauseForm.id}/`
      : `${API_URL}/api/v1/program-pauses/`;
    const method = pauseForm.id ? 'PATCH' : 'POST';
    try {
      const res = await fetch(url, {
        method,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason: pauseForm.reason || null,
          pause_start: pauseForm.pause_start,
          pause_end: pauseForm.pause_end,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        const msg = (Object.values(data) as string[][]).flat().join(' ');
        setPauseFormError(msg || 'Error saving pause.');
      } else {
        notify(pauseForm.id ? 'Pause updated.' : 'Pause created.', { type: 'success' });
        setPauseModalOpen(false);
        fetchPauses();
      }
    } catch {
      setPauseFormError('Network error saving pause.');
    }
    setPauseSaving(false);
  };

  const archivePause = async (id: number) => {
    const token = localStorage.getItem('accessToken');
    try {
      const res = await fetch(`${API_URL}/api/v1/program-pauses/${id}/archive/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        notify('Pause archived and vouchers cleaned up.', { type: 'success' });
        fetchPauses();
      } else {
        notify('Error archiving pause.', { type: 'error' });
      }
    } catch {
      notify('Error archiving pause.', { type: 'error' });
    }
  };

  const unarchivePause = async (id: number) => {
    const token = localStorage.getItem('accessToken');
    try {
      const res = await fetch(`${API_URL}/api/v1/program-pauses/${id}/unarchive/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        notify('Pause unarchived.', { type: 'success' });
        fetchPauses();
      } else {
        notify('Error unarchiving pause.', { type: 'error' });
      }
    } catch {
      notify('Error unarchiving pause.', { type: 'error' });
    }
  };

  if (loading) return <Loading />;

  return (
    <div>
      <Title title="Settings" />

      <Card sx={{ m: 2 }}>
        <CardHeader title="System Settings" />
        <CardContent>
          <Tabs value={tab} onChange={(_, v) => setTab(v)}>
            <Tab label="Order Window" />
            <Tab label="Email" />
            <Tab label="Branding" />
            <Tab label="Vouchers" />
            <Tab label="Program Pauses" />
          </Tabs>

          {/* Order Window Tab */}
          <TabPanel value={tab} index={0}>
            {orderWindow && (
              <Box sx={{ maxWidth: 560 }}>

                {/* Live status banner */}
                <Alert
                  severity={orderWindow.enabled ? (orderWindow.is_open ? 'success' : 'warning') : 'info'}
                  sx={{ mb: 3 }}
                  action={
                    orderWindow.enabled ? (
                      <Chip
                        label={orderWindow.is_open ? 'OPEN' : 'CLOSED'}
                        color={orderWindow.is_open ? 'success' : 'warning'}
                        size="small"
                        sx={{ fontWeight: 'bold', mt: 0.5 }}
                      />
                    ) : undefined
                  }
                >
                  <AlertTitle>
                    {!orderWindow.enabled
                      ? 'Order window restrictions are disabled — participants can order anytime'
                      : orderWindow.is_open
                      ? 'Order window is currently open'
                      : 'Order window is currently closed'}
                  </AlertTitle>
                  {orderWindow.enabled && orderWindow.is_open && orderWindow.next_closes_at && (
                    <>Closes at <strong>{new Date(orderWindow.next_closes_at).toLocaleString()}</strong></>
                  )}
                  {orderWindow.enabled && !orderWindow.is_open && orderWindow.next_opens_at && (
                    <>Opens at <strong>{new Date(orderWindow.next_opens_at).toLocaleString()}</strong></>
                  )}
                  {orderWindow.enabled && !orderWindow.is_open && !orderWindow.next_opens_at && (
                    <>No upcoming class scheduled — check that programs have a meeting day and time set.</>
                  )}
                </Alert>

                <FormControlLabel
                  control={
                    <Switch
                      checked={orderWindow.enabled}
                      onChange={(e) =>
                        setOrderWindow({ ...orderWindow, enabled: e.target.checked })
                      }
                    />
                  }
                  label="Enable Order Window Restrictions"
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  type="number"
                  label="Hours Before Class (Window Opens)"
                  value={orderWindow.hours_before_class}
                  onChange={(e) =>
                    setOrderWindow({
                      ...orderWindow,
                      hours_before_class: parseInt(e.target.value) || 0,
                    })
                  }
                  helperText="Orders can be placed this many hours before class starts (1–168)"
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  type="number"
                  label="Hours Before Close (Window Closes)"
                  value={orderWindow.hours_before_close}
                  onChange={(e) =>
                    setOrderWindow({
                      ...orderWindow,
                      hours_before_close: parseInt(e.target.value) || 0,
                    })
                  }
                  helperText="Orders must be placed at least this many hours before class (0 = right up until class time)"
                  sx={{ mb: 3 }}
                />

                <Button
                  variant="contained"
                  onClick={saveOrderWindow}
                  disabled={saving}
                >
                  Save Order Window Settings
                </Button>
              </Box>
            )}
          </TabPanel>

          {/* Email Tab */}
          <TabPanel value={tab} index={1}>
            {email && (
              <Box sx={{ maxWidth: 500 }}>
                <TextField
                  fullWidth
                  label="Default From Email"
                  value={email.from_email_default}
                  onChange={(e) =>
                    setEmail({ ...email, from_email_default: e.target.value })
                  }
                  helperText="Leave blank to use system default"
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  label="Reply-To Email"
                  value={email.reply_to_default}
                  onChange={(e) =>
                    setEmail({ ...email, reply_to_default: e.target.value })
                  }
                  sx={{ mb: 2 }}
                />

                <Alert severity="info" sx={{ mb: 3 }}>
                  Effective From Email: {email.effective_from_email || 'System Default'}
                </Alert>

                <Button variant="contained" onClick={saveEmail} disabled={saving}>
                  Save Email Settings
                </Button>
              </Box>
            )}
          </TabPanel>

          {/* Branding Tab */}
          <TabPanel value={tab} index={2}>
            {branding && (
              <Box sx={{ maxWidth: 500 }}>
                <TextField
                  fullWidth
                  label="Organization Name"
                  value={branding.organization_name}
                  onChange={(e) =>
                    setBranding({ ...branding, organization_name: e.target.value })
                  }
                  helperText="Displayed on printed orders and documents"
                  sx={{ mb: 3 }}
                />

                {branding.logo && (
                  <Box sx={{ mb: 2 }}>
                    <img
                      src={branding.logo}
                      alt="Organization Logo"
                      style={{ maxWidth: 200, maxHeight: 100 }}
                    />
                  </Box>
                )}

                <Button variant="contained" onClick={saveBranding} disabled={saving}>
                  Save Branding Settings
                </Button>
              </Box>
            )}
          </TabPanel>

          {/* Voucher Tab */}
          <TabPanel value={tab} index={3}>
            {voucher ? (
              <Box sx={{ maxWidth: 500 }}>
                <TextField
                  fullWidth
                  type="number"
                  label="Adult Amount ($)"
                  value={voucher.adult_amount}
                  onChange={(e) =>
                    setVoucher({
                      ...voucher,
                      adult_amount: parseFloat(e.target.value) || 0,
                    })
                  }
                  inputProps={{ step: 0.5 }}
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  type="number"
                  label="Child Amount ($)"
                  value={voucher.child_amount}
                  onChange={(e) =>
                    setVoucher({
                      ...voucher,
                      child_amount: parseFloat(e.target.value) || 0,
                    })
                  }
                  inputProps={{ step: 0.5 }}
                  sx={{ mb: 2 }}
                />

                <TextField
                  fullWidth
                  type="number"
                  label="Infant Modifier ($)"
                  value={voucher.infant_modifier}
                  onChange={(e) =>
                    setVoucher({
                      ...voucher,
                      infant_modifier: parseFloat(e.target.value) || 0,
                    })
                  }
                  inputProps={{ step: 0.5 }}
                  helperText="Additional amount added for infants"
                  sx={{ mb: 3 }}
                />

                <Button variant="contained" onClick={saveVoucher} disabled={saving}>
                  Save Voucher Settings
                </Button>
              </Box>
            ) : (
              <Alert severity="warning">
                No active voucher settings found. Create one in the Voucher
                Settings resource.
              </Alert>
            )}
          </TabPanel>
          {/* Program Pauses Tab */}
          <TabPanel value={tab} index={4}>
            <Box sx={{ maxWidth: 860 }}>

              {/* Active pause alert */}
              {activePause && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                  <AlertTitle>Pause Is Active</AlertTitle>
                  {activePause.reason} — This Pause Is Active
                </Alert>
              )}

              {/* Header row */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">Program Pauses</Typography>
                <Button variant="contained" onClick={openCreateModal}>+ Create Pause</Button>
              </Box>

              <Divider sx={{ mb: 2 }} />

              {/* Pause table */}
              {pausesLoading ? (
                <CircularProgress />
              ) : pauses.length === 0 ? (
                <Alert severity="info">No program pauses found.</Alert>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Reason</TableCell>
                      <TableCell>Start</TableCell>
                      <TableCell>End</TableCell>
                      <TableCell>Multiplier</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {pauses.map((pause) => (
                      <TableRow key={pause.id}>
                        <TableCell>{pause.reason || '—'}</TableCell>
                        <TableCell>{new Date(pause.pause_start).toLocaleString()}</TableCell>
                        <TableCell>{new Date(pause.pause_end).toLocaleString()}</TableCell>
                        <TableCell>{pause.multiplier}×</TableCell>
                        <TableCell>
                          {pause.archived ? (
                            <Chip label="🗄️ Archived" size="small" variant="outlined" />
                          ) : pause.is_active ? (
                            <Chip label="Active" size="small" color="warning" />
                          ) : (
                            <Chip label="Upcoming" size="small" color="info" />
                          )}
                        </TableCell>
                        <TableCell align="right">
                          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                            {!pause.archived && (
                              <Button size="small" variant="outlined" onClick={() => openEditModal(pause)}>
                                Edit
                              </Button>
                            )}
                            {pause.archived ? (
                              <Button size="small" color="secondary" onClick={() => unarchivePause(pause.id)}>
                                Unarchive
                              </Button>
                            ) : (
                              <Button size="small" color="warning" onClick={() => archivePause(pause.id)}>
                                Archive
                              </Button>
                            )}
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}

              {/* Create / Edit Modal */}
              <Dialog open={pauseModalOpen} onClose={() => setPauseModalOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>{pauseForm.id ? 'Edit Pause' : 'Create Pause'}</DialogTitle>
                <DialogContent>
                  <Box sx={{ pt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Alert severity="info" sx={{ fontSize: '0.8rem' }}>
                      Pause must start ≥11 days from today · max 14 days duration · only one pause at a time
                    </Alert>

                    <TextField
                      fullWidth
                      label="Reason"
                      value={pauseForm.reason}
                      onChange={(e) => setPauseForm({ ...pauseForm, reason: e.target.value })}
                      placeholder="e.g. Holiday break"
                    />

                    <TextField
                      fullWidth
                      label="Pause Start"
                      type="datetime-local"
                      value={pauseForm.pause_start}
                      onChange={(e) => setPauseForm({ ...pauseForm, pause_start: e.target.value })}
                      InputLabelProps={{ shrink: true }}
                    />

                    <TextField
                      fullWidth
                      label="Pause End"
                      type="datetime-local"
                      value={pauseForm.pause_end}
                      onChange={(e) => setPauseForm({ ...pauseForm, pause_end: e.target.value })}
                      InputLabelProps={{ shrink: true }}
                    />

                    {overlapError && (
                      <Alert severity="error">{overlapError}</Alert>
                    )}

                    {pauseFormError && (
                      <Alert severity="error">{pauseFormError}</Alert>
                    )}
                  </Box>
                </DialogContent>
                <DialogActions>
                  <Button onClick={() => setPauseModalOpen(false)}>Cancel</Button>
                  <Button
                    variant="contained"
                    onClick={savePause}
                    disabled={pauseSaving || !!overlapError}
                  >
                    {pauseSaving ? <CircularProgress size={20} /> : (pauseForm.id ? 'Save Changes' : 'Create Pause')}
                  </Button>
                </DialogActions>
              </Dialog>

            </Box>
          </TabPanel>
        </CardContent>
      </Card>
    </div>
  );
};

export default Settings;
