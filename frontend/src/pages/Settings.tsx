/**
 * Settings Page
 *
 * Manage system-wide settings including order window, email, and branding.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
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
  Collapse,
  IconButton,
  Tooltip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { API_URL } from '../utils/apiUrl';
import { useDebounce } from '../utils/useDebounce';

const getCsrfToken = (): string =>
  document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] ?? '';

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
  last_resync_at: string | null;
  last_resync_by_username: string | null;
}

interface PauseFormData {
  id: number | null;
  reason: string;
  pause_start: string;
  pause_end: string;
}

interface HygieneSettings {
  id: number;
  hygiene_ratio: number;
  enabled: boolean;
}

// ---------------------------------------------------------------------------
// Order Window Dashboard types
// ---------------------------------------------------------------------------

type WindowStatus = 'open' | 'closed' | 'force_open' | 'force_closed' | 'disabled' | 'no_schedule';

interface WindowCycle {
  meeting_at: string;
  opens_at: string;
  closes_at: string;
}

interface ActiveOverride {
  id: number;
  force_status: 'open' | 'closed';
  expires_at: string;
  reason: string;
  created_by_username: string | null;
  is_active: boolean;
}

interface EffectiveConfig {
  hours_before_class: number;
  hours_before_close: number;
  enabled: boolean;
  is_overridden: boolean;
  hours_before_class_source: 'program' | 'global';
  hours_before_close_source: 'program' | 'global';
  enabled_source: 'program' | 'global';
}

interface ProgramWindowStatus {
  program_id: number;
  program_name: string;
  meeting_day: string;
  meeting_time: string;
  window_status: WindowStatus;
  cycles: WindowCycle[];
  seconds_until_change: number | null;
  active_order_count: number;
  override: ActiveOverride | null;
  config: EffectiveConfig;
}

interface OrderWindowDashboardData {
  programs: ProgramWindowStatus[];
  global: OrderWindowSettings;
  as_of: string;
}

// ---------------------------------------------------------------------------
// Status badge helpers
// ---------------------------------------------------------------------------

const STATUS_META: Record<WindowStatus, { label: string; color: 'success' | 'warning' | 'error' | 'default' | 'info' }> = {
  open: { label: 'OPEN', color: 'success' },
  closed: { label: 'CLOSED', color: 'default' },
  force_open: { label: 'FORCE OPEN', color: 'warning' },
  force_closed: { label: 'FORCE CLOSED', color: 'error' },
  disabled: { label: 'DISABLED', color: 'info' },
  no_schedule: { label: 'NO SCHEDULE', color: 'default' },
};

const fmt = (iso: string) => new Date(iso).toLocaleString(undefined, {
  weekday: 'short', month: 'short', day: 'numeric',
  hour: 'numeric', minute: '2-digit',
});

function useCountdown(seconds: number | null): string {
  const [display, setDisplay] = useState('');
  useEffect(() => {
    if (seconds === null) { setDisplay(''); return; }
    const tick = () => {
      const s = Math.max(0, seconds - Math.floor((Date.now() - start) / 1000));
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      const sec = s % 60;
      setDisplay(h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${sec}s` : `${sec}s`);
    };
    const start = Date.now();
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [seconds]);
  return display;
}

// ---------------------------------------------------------------------------
// CycleTimeline — visual strip of the next 3 windows
// ---------------------------------------------------------------------------

const CycleTimeline = ({ cycles }: { cycles: WindowCycle[] }) => (
  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 1 }}>
    {cycles.map((c, i) => (
      <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '0.78rem' }}>
        <Chip label={i === 0 ? 'Next' : `+${i}wk`} size="small" sx={{ minWidth: 46, fontSize: '0.7rem' }} />
        <Box sx={{ color: 'success.main', fontWeight: 500 }}>{fmt(c.opens_at)}</Box>
        <Box sx={{ color: 'text.disabled' }}>→</Box>
        <Box sx={{ color: 'error.main' }}>{fmt(c.closes_at)}</Box>
        <Box sx={{ color: 'text.secondary' }}>· class {fmt(c.meeting_at)}</Box>
      </Box>
    ))}
  </Box>
);

// ---------------------------------------------------------------------------
// InlineConfigPanel — per-program config override fields
// ---------------------------------------------------------------------------

const InlineConfigPanel = ({
  programId,
  config,
  onSaved,
}: {
  programId: number;
  config: EffectiveConfig;
  onSaved: () => void;
}) => {
  const notify = useNotify();
  const [hbc, setHbc] = useState<string>(String(config.hours_before_class));
  const [hbcl, setHbcl] = useState<string>(String(config.hours_before_close));
  const [enabled, setEnabled] = useState<boolean>(config.enabled);
  const [saving, setSaving] = useState(false);

  const isOverriding = config.is_overridden;

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/programs/${programId}/order-window/`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({
          hours_before_class: parseInt(hbc) || null,
          hours_before_close: parseInt(hbcl) || null,
          enabled,
        }),
      });
      if (res.ok) { notify('Program window config saved.', { type: 'success' }); onSaved(); }
      else { notify('Error saving config.', { type: 'error' }); }
    } catch { notify('Network error.', { type: 'error' }); }
    setSaving(false);
  };

  const revert = async () => {
    setSaving(true);
    try {
      await fetch(`${API_URL}/api/v1/programs/${programId}/order-window/`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
      notify('Reverted to global defaults.', { type: 'success' });
      onSaved();
    } catch { notify('Network error.', { type: 'error' }); }
    setSaving(false);
  };

  const srcLabel = (src: 'program' | 'global') =>
    src === 'global' ? <Chip label="global" size="small" variant="outlined" sx={{ ml: 1, fontSize: '0.65rem', height: 18 }} /> : null;

  return (
    <Box sx={{ mt: 1, p: 1.5, borderRadius: 1, bgcolor: 'action.hover' }}>
      <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary' }}>
        Window Config {isOverriding ? '(program override)' : '(using global defaults)'}
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, mt: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <TextField
            size="small" type="number" label="Opens (hrs before)"
            value={hbc} onChange={e => setHbc(e.target.value)}
            sx={{ width: 150 }} inputProps={{ min: 1, max: 168 }}
          />
          {srcLabel(config.hours_before_class_source)}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <TextField
            size="small" type="number" label="Closes (hrs before)"
            value={hbcl} onChange={e => setHbcl(e.target.value)}
            sx={{ width: 150 }} inputProps={{ min: 0, max: 168 }}
          />
          {srcLabel(config.hours_before_close_source)}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <FormControlLabel
            control={<Switch checked={enabled} size="small" onChange={e => setEnabled(e.target.checked)} />}
            label="Enabled"
          />
          {srcLabel(config.enabled_source)}
        </Box>
      </Box>
      <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
        <Button size="small" variant="contained" onClick={save} disabled={saving}>
          {saving ? <CircularProgress size={14} /> : 'Save'}
        </Button>
        {isOverriding && (
          <Button size="small" variant="outlined" color="warning" onClick={revert} disabled={saving}>
            Revert to Global
          </Button>
        )}
      </Box>
    </Box>
  );
};

// ---------------------------------------------------------------------------
// ManualOverridePanel — force-open / force-close with expiry
// ---------------------------------------------------------------------------

const DURATION_PRESETS = [
  { label: '1 hour', minutes: 60 },
  { label: '2 hours', minutes: 120 },
  { label: '4 hours', minutes: 240 },
  { label: 'End of today', minutes: -1 },
];

const ManualOverridePanel = ({
  programId,
  programName,
  override,
  onSaved,
}: {
  programId: number;
  programName: string;
  override: ActiveOverride | null;
  onSaved: () => void;
}) => {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const [forceStatus, setForceStatus] = useState<'open' | 'closed'>('closed');
  const [expiresAt, setExpiresAt] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!expiresAt) { notify('Expiry time is required.', { type: 'error' }); return; }
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/programs/${programId}/order-window/override/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ force_status: forceStatus, expires_at: expiresAt, reason }),
      });
      if (res.ok) {
        notify(`Override applied — window force-${forceStatus}.`, { type: 'success' });
        setOpen(false); setReason(''); onSaved();
      } else {
        const d = await res.json();
        notify(d.detail || 'Error applying override.', { type: 'error' });
      }
    } catch { notify('Network error.', { type: 'error' }); }
    setSaving(false);
  };

  const clearOverride = async () => {
    try {
      await fetch(`${API_URL}/api/v1/programs/${programId}/order-window/override/`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
      notify('Override cleared.', { type: 'success' });
      onSaved();
    } catch { notify('Network error.', { type: 'error' }); }
  };

  const setPreset = (minutes: number) => {
    const d = new Date();
    if (minutes === -1) { d.setHours(23, 59, 0, 0); }
    else { d.setMinutes(d.getMinutes() + minutes); }
    setExpiresAt(d.toISOString().slice(0, 16));
  };

  if (override) {
    return (
      <Box sx={{ mt: 1, p: 1.5, borderRadius: 1, bgcolor: 'warning.lighter', border: '1px solid', borderColor: 'warning.main' }}>
        <Typography variant="caption" sx={{ fontWeight: 600 }}>
          ⚠️ Override active — force {override.force_status} until {fmt(override.expires_at)}
          {override.created_by_username && ` · set by ${override.created_by_username}`}
        </Typography>
        {override.reason && <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>{override.reason}</Typography>}
        <Button size="small" variant="outlined" color="warning" sx={{ mt: 1 }} onClick={clearOverride}>
          Clear Override
        </Button>
      </Box>
    );
  }

  return (
    <>
      <Button size="small" variant="outlined" sx={{ mt: 1 }} onClick={() => setOpen(true)}>
        Manual Override
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Override: {programName}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', gap: 1, mb: 2, mt: 1 }}>
            {(['closed', 'open'] as const).map(s => (
              <Button
                key={s}
                variant={forceStatus === s ? 'contained' : 'outlined'}
                color={s === 'open' ? 'success' : 'error'}
                onClick={() => setForceStatus(s)}
                fullWidth
              >
                Force {s === 'open' ? '🔓 Open' : '🔒 Closed'}
              </Button>
            ))}
          </Box>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
            Quick expiry:
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 2 }}>
            {DURATION_PRESETS.map(p => (
              <Chip key={p.label} label={p.label} size="small" onClick={() => setPreset(p.minutes)} clickable />
            ))}
          </Box>
          <TextField
            fullWidth size="small" label="Expires at" type="datetime-local"
            value={expiresAt} onChange={e => setExpiresAt(e.target.value)}
            InputLabelProps={{ shrink: true }} sx={{ mb: 2 }}
          />
          <TextField
            fullWidth size="small" label="Reason (optional)"
            value={reason} onChange={e => setReason(e.target.value)}
            placeholder="e.g. inventory audit"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submit} disabled={saving}>
            {saving ? <CircularProgress size={16} /> : 'Apply Override'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

// ---------------------------------------------------------------------------
// ProgramWindowRow — one row in the dashboard table
// ---------------------------------------------------------------------------

const ProgramWindowRow = ({
  program,
  onRefresh,
}: {
  program: ProgramWindowStatus;
  onRefresh: () => void;
}) => {
  const [expanded, setExpanded] = useState(false);
  const countdown = useCountdown(program.seconds_until_change);
  const meta = STATUS_META[program.window_status];

  return (
    <>
      <TableRow sx={{ '& td': { verticalAlign: 'middle' } }}>
        <TableCell sx={{ fontWeight: 500 }}>{program.program_name}</TableCell>
        <TableCell sx={{ textTransform: 'capitalize' }}>
          {program.meeting_day} {program.meeting_time.slice(0, 5)}
        </TableCell>
        <TableCell>
          <Chip label={meta.label} color={meta.color} size="small" sx={{ fontWeight: 700, letterSpacing: 0.5 }} />
        </TableCell>
        <TableCell sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>
          {countdown && (
            <Tooltip title={
              program.window_status === 'open' ? 'Closes in' :
              program.window_status === 'closed' ? 'Opens in' : 'Changes in'
            }>
              <span>{countdown}</span>
            </Tooltip>
          )}
        </TableCell>
        <TableCell align="center">
          <Chip label={program.active_order_count} size="small" variant="outlined" />
        </TableCell>
        <TableCell>
          <IconButton size="small" onClick={() => setExpanded(e => !e)}>
            {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
          </IconButton>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell colSpan={6} sx={{ p: 0, borderBottom: expanded ? undefined : 'none' }}>
          <Collapse in={expanded} timeout="auto" unmountOnExit>
            <Box sx={{ p: 2, bgcolor: 'action.hover' }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', display: 'block', mb: 0.5 }}>
                Upcoming Windows
              </Typography>
              <CycleTimeline cycles={program.cycles} />
              <Divider sx={{ my: 1.5 }} />
              <InlineConfigPanel
                programId={program.program_id}
                config={program.config}
                onSaved={onRefresh}
              />
              <Divider sx={{ my: 1.5 }} />
              <ManualOverridePanel
                programId={program.program_id}
                programName={program.program_name}
                override={program.override}
                onSaved={onRefresh}
              />
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
};

// ---------------------------------------------------------------------------
// OrderWindowDashboard — the full tab content
// ---------------------------------------------------------------------------

const OrderWindowDashboard = ({
  globalSettings,
  onSaveGlobal,
  saving,
}: {
  globalSettings: OrderWindowSettings;
  onSaveGlobal: (settings: OrderWindowSettings) => void;
  saving: boolean;
}) => {
  const [global, setGlobal] = useState(globalSettings);
  const [dashboard, setDashboard] = useState<OrderWindowDashboardData | null>(null);
  const [dashLoading, setDashLoading] = useState(true);
  const [asOf, setAsOf] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/order-windows/status/`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data: OrderWindowDashboardData = await res.json();
        setDashboard(data);
        setAsOf(data.as_of);
      }
    } catch {
      // silent — stale data is still useful
    }
    setDashLoading(false);
  }, []);

  useEffect(() => {
    fetchDashboard();
    pollRef.current = setInterval(fetchDashboard, 30_000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchDashboard]);

  const saveGlobal = async () => {
    onSaveGlobal(global);
  };

  const secondsAgo = asOf
    ? Math.round((Date.now() - new Date(asOf).getTime()) / 1000)
    : null;

  return (
    <Box>
      {/* Global defaults panel */}
      <Box sx={{ maxWidth: 560, mb: 4 }}>
        <Typography variant="h6" sx={{ mb: 2, fontSize: '0.95rem', fontWeight: 600 }}>
          Global Defaults
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
          Programs without a custom override inherit these values.
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <TextField
            size="small" type="number" label="Opens (hrs before class)"
            value={global.hours_before_class}
            onChange={e => setGlobal({ ...global, hours_before_class: parseInt(e.target.value) || 0 })}
            helperText="1–168 hours" sx={{ width: 200 }}
          />
          <TextField
            size="small" type="number" label="Closes (hrs before class)"
            value={global.hours_before_close}
            onChange={e => setGlobal({ ...global, hours_before_close: parseInt(e.target.value) || 0 })}
            helperText="0 = closes at class time" sx={{ width: 200 }}
          />
          <FormControlLabel
            control={
              <Switch
                checked={global.enabled}
                onChange={e => setGlobal({ ...global, enabled: e.target.checked })}
              />
            }
            label="Enabled"
            sx={{ mt: 0.5 }}
          />
        </Box>
        <Button variant="contained" sx={{ mt: 2 }} onClick={saveGlobal} disabled={saving}>
          Save Global Defaults
        </Button>
      </Box>

      <Divider sx={{ mb: 3 }} />

      {/* Live program status table */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6" sx={{ fontSize: '0.95rem', fontWeight: 600 }}>
          Live Program Status
        </Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {secondsAgo !== null ? `Updated ${secondsAgo}s ago` : ''}
          <Button size="small" sx={{ ml: 1 }} onClick={fetchDashboard}>↻ Refresh</Button>
        </Typography>
      </Box>

      {dashLoading ? (
        <CircularProgress size={24} />
      ) : !dashboard || dashboard.programs.length === 0 ? (
        <Alert severity="info">No programs found.</Alert>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Program</TableCell>
              <TableCell>Schedule</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Changes In</TableCell>
              <TableCell align="center">Active Orders</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {dashboard.programs.map(p => (
              <ProgramWindowRow
                key={p.program_id}
                program={p}
                onRefresh={fetchDashboard}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  );
};

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
  const [hygiene, setHygiene] = useState<HygieneSettings | null>(null);

  // Program Pauses state
  const [pauses, setPauses] = useState<ProgramPause[]>([]);
  const [activePause, setActivePause] = useState<ProgramPause | null>(null);
  const [pauseForm, setPauseForm] = useState<PauseFormData>({ id: null, reason: '', pause_start: '', pause_end: '' });
  const [pauseModalOpen, setPauseModalOpen] = useState(false);
  const [pauseFormError, setPauseFormError] = useState<string | null>(null);
  const [overlapError, setOverlapError] = useState<string | null>(null);
  const [pauseSaving, setPauseSaving] = useState(false);
  const [pausesLoading, setPausesLoading] = useState(false);
  const [resyncingPause, setResyncingPause] = useState<number | null>(null);

  // Hygiene Settings state
  const [hygieneConfirmOpen, setHygieneConfirmOpen] = useState(false);
  const [pendingHygiene, setPendingHygiene] = useState<HygieneSettings | null>(null);

  // Debounced pause form dates for real-time overlap check
  const debouncedPauseStart = useDebounce(pauseForm.pause_start, 500);
  const debouncedPauseEnd = useDebounce(pauseForm.pause_end, 500);

  // Fetch all settings
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [owResponse, emailResponse, brandingResponse, voucherResponse, hygieneResponse] =
          await Promise.all([
            dataProvider.getOne('settings/order-window-settings', { id: 'current' }),
            dataProvider.getOne('settings/email-settings', { id: 'current' }),
            dataProvider.getOne('settings/branding-settings', { id: 'current' }),
            dataProvider.getList('voucher-settings', {
              pagination: { page: 1, perPage: 1 },
              filter: { active: true },
              sort: { field: 'id', order: 'DESC' },
            }),
            dataProvider.getOne('hygiene-settings', { id: 'current' }),
          ]);

        setOrderWindow(owResponse.data as OrderWindowSettings);
        setEmail(emailResponse.data as EmailSettings);
        setBranding(brandingResponse.data as BrandingSettings);
        if (voucherResponse.data.length > 0) {
          setVoucher(voucherResponse.data[0] as VoucherSettings);
        }
        setHygiene(hygieneResponse.data as HygieneSettings);
      } catch {
        notify('Error loading settings', { type: 'error' });
      }
      setLoading(false);
    };

    fetchSettings();
  }, [dataProvider, notify]);

  // Save Order Window Settings
  const saveOrderWindow = async (updatedSettings?: OrderWindowSettings) => {
    const data = updatedSettings ?? orderWindow;
    if (!data) return;
    setSaving(true);
    try {
      await dataProvider.update('settings/order-window-settings', {
        id: 'current',
        data,
        previousData: data,
      });
      setOrderWindow(data);
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

  // Save Hygiene Settings (with confirmation)
  const requestHygieneSave = () => {
    if (!hygiene) return;
    setPendingHygiene(hygiene);
    setHygieneConfirmOpen(true);
  };

  const confirmHygieneSave = async () => {
    if (!pendingHygiene) return;
    setSaving(true);
    setHygieneConfirmOpen(false);
    try {
      await dataProvider.update('hygiene-settings', {
        id: 'current',
        data: pendingHygiene,
        previousData: pendingHygiene,
      });
      notify('Hygiene settings saved', { type: 'success' });
      setHygiene(pendingHygiene);
    } catch {
      notify('Error saving settings', { type: 'error' });
    }
    setSaving(false);
    setPendingHygiene(null);
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

  const resyncPause = async (id: number) => {
    setResyncingPause(id);
    const token = localStorage.getItem('accessToken');
    try {
      const res = await fetch(`${API_URL}/api/v1/program-pauses/${id}/resync/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) {
        notify(
          `Resync complete: ${data.updated_count} vouchers updated, ${data.skipped_count} already correct.`,
          { type: 'success' }
        );
        setPauses(prev => prev.map(p => p.id === id ? data : p));
        if (activePause?.id === id) setActivePause(data);
      } else {
        notify(data.detail || 'Error resyncing pause.', { type: 'error' });
      }
    } catch {
      notify('Error resyncing pause.', { type: 'error' });
    }
    setResyncingPause(null);
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
            <Tab label="Hygiene" />
          </Tabs>

          {/* Order Window Tab */}
          <TabPanel value={tab} index={0}>
            {orderWindow ? (
              <OrderWindowDashboard
                globalSettings={orderWindow}
                onSaveGlobal={saveOrderWindow}
                saving={saving}
              />
            ) : (
              <CircularProgress size={24} />
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
                            {pause.is_active && !pause.archived && (
                              <Button
                                size="small"
                                color="error"
                                variant="outlined"
                                onClick={() => resyncPause(pause.id)}
                                disabled={resyncingPause === pause.id}
                                title={pause.last_resync_at
                                  ? `Last resync: ${new Date(pause.last_resync_at).toLocaleString()} by ${pause.last_resync_by_username}`
                                  : 'Never resynced — auto-trigger may not have fired'}
                              >
                                {resyncingPause === pause.id ? <CircularProgress size={16} /> : 'Resync'}
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

          {/* Hygiene Tab */}
          <TabPanel value={tab} index={5}>
            {hygiene && (
              <Box sx={{ maxWidth: 560 }}>

                {/* Impact warning */}
                <Alert severity="warning" sx={{ mb: 3 }}>
                  <AlertTitle>⚠️ Impact Warning</AlertTitle>
                  Changes to hygiene settings affect hygiene balance calculations immediately for all participants.
                </Alert>

                {/* Ratio guide */}
                <Alert severity="info" sx={{ mb: 3 }}>
                  <AlertTitle>Common Ratios</AlertTitle>
                  <Typography variant="body2">
                    • <strong>0.2500</strong> = 1/4 of balance (25%)<br />
                    • <strong>0.3333</strong> = 1/3 of balance (33.33%, default)<br />
                    • <strong>0.5000</strong> = 1/2 of balance (50%)
                  </Typography>
                </Alert>

                <TextField
                  fullWidth
                  type="number"
                  label="Hygiene Ratio"
                  value={hygiene.hygiene_ratio}
                  onChange={(e) =>
                    setHygiene({
                      ...hygiene,
                      hygiene_ratio: parseFloat(e.target.value) || 0,
                    })
                  }
                  inputProps={{ step: 0.0001, min: 0, max: 1 }}
                  helperText={`Percentage of available balance for hygiene products (${(hygiene.hygiene_ratio * 100).toFixed(2)}%)`}
                  sx={{ mb: 2 }}
                />

                <FormControlLabel
                  control={
                    <Switch
                      checked={hygiene.enabled}
                      onChange={(e) =>
                        setHygiene({ ...hygiene, enabled: e.target.checked })
                      }
                    />
                  }
                  label="Enable Hygiene Balance Calculation"
                  sx={{ mb: 3 }}
                />

                <Button
                  variant="contained"
                  onClick={requestHygieneSave}
                  disabled={saving}
                >
                  Save Hygiene Settings
                </Button>
              </Box>
            )}
          </TabPanel>

          {/* Hygiene Confirmation Dialog */}
          <Dialog
            open={hygieneConfirmOpen}
            onClose={() => setHygieneConfirmOpen(false)}
            maxWidth="sm"
            fullWidth
          >
            <DialogTitle>⚠️ Confirm Hygiene Settings Change</DialogTitle>
            <DialogContent>
              <Alert severity="warning" sx={{ mb: 2 }}>
                This will affect hygiene balance calculations <strong>immediately</strong> for all participants.
              </Alert>
              {pendingHygiene && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body1" gutterBottom>
                    <strong>New Ratio:</strong> {pendingHygiene.hygiene_ratio} ({(pendingHygiene.hygiene_ratio * 100).toFixed(2)}%)
                  </Typography>
                  <Typography variant="body1">
                    <strong>Enabled:</strong> {pendingHygiene.enabled ? 'Yes' : 'No'}
                  </Typography>
                </Box>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setHygieneConfirmOpen(false)}>Cancel</Button>
              <Button
                variant="contained"
                color="warning"
                onClick={confirmHygieneSave}
                disabled={saving}
              >
                {saving ? <CircularProgress size={20} /> : 'Confirm Save'}
              </Button>
            </DialogActions>
          </Dialog>

        </CardContent>
      </Card>
    </div>
  );
};

export default Settings;
