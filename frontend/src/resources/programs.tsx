/**
 * Program Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  NumberField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  SelectInput,
  Show,
  EditButton,
  ShowButton,
  ReferenceManyField,
  useRecordContext,
  TabbedShowLayout,
  FunctionField,
  Button,
  useGetList,
} from 'react-admin';
import { Box, Chip, Typography, Table, TableHead, TableBody, TableRow, TableCell, CircularProgress, Alert, Button as MuiButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField as MuiTextField, FormControlLabel, Switch } from '@mui/material';
import { useState, useEffect, useCallback } from 'react';
import { API_URL } from '../utils/apiUrl';
import { useNavigate } from 'react-router-dom';

const getCsrfToken = (): string =>
  document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] ?? '';

const MEETING_DAY_CHOICES = [
  { id: 'monday', name: 'Monday' },
  { id: 'tuesday', name: 'Tuesday' },
  { id: 'wednesday', name: 'Wednesday' },
  { id: 'thursday', name: 'Thursday' },
  { id: 'friday', name: 'Friday' },
];

const SPLIT_STRATEGY_CHOICES = [
  { id: 'none', name: 'None (Single Packer)' },
  { id: 'fifty_fifty', name: '50/50 Split' },
  { id: 'round_robin', name: 'Round Robin' },
];

const STRATEGY_LABELS: Record<string, string> = {
  none: 'None (Single Packer)',
  fifty_fifty: '50/50 Split',
  round_robin: 'Round Robin',
  by_category: 'By Category',
};

export const ProgramList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="show">
      <TextField source="name" />
      <TextField source="MeetingDay" label="Meeting Day" />
      <TextField source="meeting_time" label="Time" />
      <NumberField source="participant_count" label="Participants" />
      <TextField source="default_split_strategy" label="Split Strategy" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

// ---------------------------------------------------------------------------
// OrderWindowTab — per-program order window status and config inside ProgramShow
// ---------------------------------------------------------------------------

type WindowStatus = 'open' | 'closed' | 'force_open' | 'force_closed' | 'disabled' | 'no_schedule';

interface WindowCycle { meeting_at: string; opens_at: string; closes_at: string; }
interface ActiveOverride { id: number; force_status: 'open' | 'closed'; expires_at: string; reason: string; created_by_username: string | null; is_active: boolean; }
interface EffectiveConfig { hours_before_class: number; hours_before_close: number; enabled: boolean; is_overridden: boolean; hours_before_class_source: 'program' | 'global'; hours_before_close_source: 'program' | 'global'; enabled_source: 'program' | 'global'; }
interface ProgramWindowStatus { program_id: number; program_name: string; meeting_day: string; meeting_time: string; window_status: WindowStatus; cycles: WindowCycle[]; seconds_until_change: number | null; active_order_count: number; override: ActiveOverride | null; config: EffectiveConfig; }

const STATUS_COLORS: Record<WindowStatus, 'success' | 'warning' | 'error' | 'default' | 'info'> = {
  open: 'success', closed: 'default', force_open: 'warning', force_closed: 'error', disabled: 'info', no_schedule: 'default',
};
const STATUS_LABELS: Record<WindowStatus, string> = {
  open: 'OPEN', closed: 'CLOSED', force_open: 'FORCE OPEN', force_closed: 'FORCE CLOSED', disabled: 'DISABLED', no_schedule: 'NO SCHEDULE',
};
const fmt = (iso: string) => new Date(iso).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

const OrderWindowTab = () => {
  const record = useRecordContext();
  const [status, setStatus] = useState<ProgramWindowStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [hbc, setHbc] = useState('');
  const [hbcl, setHbcl] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [forceStatus, setForceStatus] = useState<'open' | 'closed'>('closed');
  const [expiresAt, setExpiresAt] = useState('');
  const [reason, setReason] = useState('');

  const fetchStatus = useCallback(async () => {
    if (!record?.id) return;
    const res = await fetch(`${API_URL}/api/v1/programs/${record.id}/order-window/`, {
      credentials: 'include',
    });
    if (res.ok) {
      const data: ProgramWindowStatus = await res.json();
      setStatus(data);
      setHbc(String(data.config.hours_before_class));
      setHbcl(String(data.config.hours_before_close));
      setEnabled(data.config.enabled);
    }
    setLoading(false);
  }, [record?.id]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const saveConfig = async () => {
    if (!record?.id) return;
    setSaving(true);
    await fetch(`${API_URL}/api/v1/programs/${record.id}/order-window/`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ hours_before_class: parseInt(hbc) || null, hours_before_close: parseInt(hbcl) || null, enabled }),
    });
    setSaving(false);
    fetchStatus();
  };

  const revertConfig = async () => {
    if (!record?.id) return;
    setSaving(true);
    await fetch(`${API_URL}/api/v1/programs/${record.id}/order-window/`, {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    setSaving(false);
    fetchStatus();
  };

  const applyOverride = async () => {
    if (!record?.id) return;
    await fetch(`${API_URL}/api/v1/programs/${record.id}/order-window/override/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ force_status: forceStatus, expires_at: expiresAt, reason }),
    });
    setOverrideOpen(false);
    fetchStatus();
  };

  const clearOverride = async () => {
    if (!record?.id) return;
    await fetch(`${API_URL}/api/v1/programs/${record.id}/order-window/override/`, {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    fetchStatus();
  };

  const setPreset = (minutes: number) => {
    const d = new Date();
    if (minutes === -1) d.setHours(23, 59, 0, 0);
    else d.setMinutes(d.getMinutes() + minutes);
    setExpiresAt(d.toISOString().slice(0, 16));
  };

  if (loading) return <CircularProgress size={24} sx={{ m: 2 }} />;
  if (!status) return <Alert severity="error">Could not load order window status.</Alert>;

  const { window_status, cycles, override, config, active_order_count } = status;

  return (
    <Box sx={{ p: 2, maxWidth: 700 }}>
      {/* Status banner */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Chip label={STATUS_LABELS[window_status]} color={STATUS_COLORS[window_status]} sx={{ fontWeight: 700, fontSize: '0.85rem', px: 1 }} />
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {active_order_count} active order{active_order_count !== 1 ? 's' : ''}
        </Typography>
      </Box>

      {/* Override banner */}
      {override && (
        <Alert severity="warning" sx={{ mb: 2 }}
          action={<MuiButton size="small" color="inherit" onClick={clearOverride}>Clear</MuiButton>}>
          Override active — force {override.force_status} until {fmt(override.expires_at)}
          {override.reason ? ` · ${override.reason}` : ''}
        </Alert>
      )}

      {/* Cycle timeline */}
      {cycles.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', display: 'block', mb: 1 }}>
            Upcoming Windows
          </Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Week</TableCell><TableCell>Opens</TableCell><TableCell>Closes</TableCell><TableCell>Class</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {cycles.map((c, i) => (
                <TableRow key={i}>
                  <TableCell><Chip label={i === 0 ? 'Next' : `+${i}wk`} size="small" /></TableCell>
                  <TableCell sx={{ color: 'success.main', fontSize: '0.8rem' }}>{fmt(c.opens_at)}</TableCell>
                  <TableCell sx={{ color: 'error.main', fontSize: '0.8rem' }}>{fmt(c.closes_at)}</TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>{fmt(c.meeting_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}

      {/* Config */}
      <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary', display: 'block', mb: 1 }}>
        Window Config {config.is_overridden ? '(program override)' : '(global defaults)'}
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center', mb: 1.5 }}>
        <MuiTextField size="small" type="number" label="Opens (hrs before)" value={hbc} onChange={e => setHbc(e.target.value)} sx={{ width: 170 }} />
        <MuiTextField size="small" type="number" label="Closes (hrs before)" value={hbcl} onChange={e => setHbcl(e.target.value)} sx={{ width: 170 }} />
        <FormControlLabel control={<Switch checked={enabled} size="small" onChange={e => setEnabled(e.target.checked)} />} label="Enabled" />
      </Box>
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <MuiButton variant="contained" size="small" onClick={saveConfig} disabled={saving}>Save Config</MuiButton>
        {config.is_overridden && (
          <MuiButton variant="outlined" size="small" color="warning" onClick={revertConfig} disabled={saving}>Revert to Global</MuiButton>
        )}
        <MuiButton variant="outlined" size="small" onClick={() => setOverrideOpen(true)}>Manual Override</MuiButton>
      </Box>

      {/* Override dialog */}
      <Dialog open={overrideOpen} onClose={() => setOverrideOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Manual Override</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', gap: 1, mb: 2, mt: 1 }}>
            {(['closed', 'open'] as const).map(s => (
              <MuiButton key={s} fullWidth variant={forceStatus === s ? 'contained' : 'outlined'} color={s === 'open' ? 'success' : 'error'} onClick={() => setForceStatus(s)}>
                Force {s === 'open' ? '🔓 Open' : '🔒 Closed'}
              </MuiButton>
            ))}
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 2 }}>
            {[{ label: '1hr', m: 60 }, { label: '2hr', m: 120 }, { label: '4hr', m: 240 }, { label: 'End of today', m: -1 }].map(p => (
              <Chip key={p.label} label={p.label} size="small" clickable onClick={() => setPreset(p.m)} />
            ))}
          </Box>
          <MuiTextField fullWidth size="small" label="Expires at" type="datetime-local" value={expiresAt} onChange={e => setExpiresAt(e.target.value)} InputLabelProps={{ shrink: true }} sx={{ mb: 2 }} />
          <MuiTextField fullWidth size="small" label="Reason (optional)" value={reason} onChange={e => setReason(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <MuiButton onClick={() => setOverrideOpen(false)}>Cancel</MuiButton>
          <MuiButton variant="contained" onClick={applyOverride}>Apply</MuiButton>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

const ProgramTitle = () => {
  const record = useRecordContext();
  return <span>Program: {record?.name || ''}</span>;
};

export const ProgramShow = () => {
  const navigate = useNavigate();
  return (
    <Show title={<ProgramTitle />}>
      <TabbedShowLayout>
        <TabbedShowLayout.Tab label="Details">
          <TextField source="name" />
          <TextField source="MeetingDay" label="Meeting Day" />
          <TextField source="meeting_time" label="Meeting Time" />
          <TextField source="meeting_address" label="Address" />
          <FunctionField
            source="default_split_strategy"
            label="Default Split Strategy"
            render={(record: { default_split_strategy: string }) =>
              STRATEGY_LABELS[record.default_split_strategy] || record.default_split_strategy
            }
          />
          <NumberField source="participant_count" label="Total Participants" />
          <NumberField source="active_participant_count" label="Active Participants" />
          <DateField source="created_at" showTime />
          <DateField source="updated_at" showTime />
        </TabbedShowLayout.Tab>
        <TabbedShowLayout.Tab label="Participants">
          <ReferenceManyField reference="participants" target="program" label={false}>
            <Datagrid rowClick="show">
              <TextField source="customer_number" label="Customer #" />
              <TextField source="name" />
              <TextField source="email" />
              <NumberField source="adults" />
              <NumberField source="children" />
            </Datagrid>
          </ReferenceManyField>
        </TabbedShowLayout.Tab>
        <TabbedShowLayout.Tab label="Packers">
          <PackersTab navigate={navigate} />
        </TabbedShowLayout.Tab>
        <TabbedShowLayout.Tab label="Combined Orders">
          <CombinedOrdersTab />
        </TabbedShowLayout.Tab>
        <TabbedShowLayout.Tab label="Order Window">
          <OrderWindowTab />
        </TabbedShowLayout.Tab>
      </TabbedShowLayout>
    </Show>
  );
};

const CombinedOrdersTab = () => {
  const record = useRecordContext();
  const { data: combinedOrders, isPending } = useGetList(
    'combined-orders',
    {
      pagination: { page: 1, perPage: 20 },
      sort: { field: 'created_at', order: 'DESC' },
      filter: { program: record?.id },
    },
    { enabled: !!record?.id }
  );

  const grandTotal = (combinedOrders ?? []).reduce(
    (sum, co) => sum + Number(co.total_price ?? 0),
    0
  );

  if (isPending) return <Box sx={{ p: 2, color: 'text.secondary' }}>Loading…</Box>;
  if (!combinedOrders || combinedOrders.length === 0) {
    return <Box sx={{ p: 2, color: 'text.secondary' }}>No combined orders for this program yet.</Box>;
  }

  return (
    <Box sx={{ p: 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box component="h3" sx={{ m: 0, fontSize: '1rem', fontWeight: 600 }}>
          {combinedOrders.length} Combined Order{combinedOrders.length !== 1 ? 's' : ''}
        </Box>
        <Box sx={{
          fontWeight: 700,
          fontSize: '1rem',
          px: 2, py: 0.5,
          borderRadius: 2,
          bgcolor: 'primary.main',
          color: 'primary.contrastText',
        }}>
          Grand Total: ${grandTotal.toFixed(2)}
        </Box>
      </Box>

      <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'rgba(0,0,0,0.04)' }}>
              {['Name', 'Week', 'Orders', 'Split Strategy', 'Total Price', 'Created', ''].map(h => (
                <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: '0.8rem', fontWeight: 600, borderBottom: '1px solid rgba(0,0,0,0.12)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {combinedOrders.map((co, i) => (
              <tr key={co.id} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.02)' }}>
                <td style={{ padding: '8px 12px', fontSize: '0.875rem' }}>{co.name}</td>
                <td style={{ padding: '8px 12px', fontSize: '0.875rem' }}>
                  {co.week ? `Wk ${co.week}, ${co.year}` : '—'}
                </td>
                <td style={{ padding: '8px 12px', fontSize: '0.875rem' }}>
                  <Chip label={co.order_count ?? (co.orders?.length ?? 0)} size="small" />
                </td>
                <td style={{ padding: '8px 12px', fontSize: '0.875rem', textTransform: 'capitalize' }}>
                  {(co.split_strategy ?? 'none').replace('_', ' ')}
                </td>
                <td style={{ padding: '8px 12px', fontSize: '0.875rem', fontWeight: 600, color: '#2e7d32' }}>
                  ${Number(co.total_price ?? 0).toFixed(2)}
                </td>
                <td style={{ padding: '8px 12px', fontSize: '0.8rem', color: '#888' }}>
                  {new Date(co.created_at).toLocaleDateString()}
                </td>
                <td style={{ padding: '8px 12px' }}>
                  <a href={`#/combined-orders/${co.id}/show`} style={{ fontSize: '0.8rem' }}>View →</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Box>
    </Box>
  );
};

const PackersTab = ({ navigate }: { navigate: ReturnType<typeof useNavigate> }) => {
  return (
    <Box sx={{ p: 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Box component="h3" sx={{ m: 0, fontSize: '1rem', fontWeight: 600 }}>Assigned Packers</Box>
        <Button
          label="Create Packer"
          onClick={() => navigate('/order-packers/create')}
          size="small"
          variant="contained"
        />
      </Box>
      <Box sx={{ color: 'text.secondary', fontSize: '0.85rem', mb: 2 }}>
        Orders are split evenly across all assigned packers. One packer gets all orders; two packers split in half; three get thirds; etc.
      </Box>
      <ReferenceManyField reference="order-packers" target="programs" label={false}>
        <Datagrid
          bulkActionButtons={false}
          empty={
            <Box sx={{ color: 'text.secondary', py: 2, pl: 1 }}>
              No packers assigned to this program yet.
            </Box>
          }
        >
          <TextField source="name" label="Packer" />
          <FunctionField
            label="All Programs"
            render={(rec: { program_names: string[] }) =>
              (rec.program_names || []).join(', ') || '—'
            }
          />
          <FunctionField
            label=""
            render={(rec: { id: number }) => (
              <Button
                label="Edit Packer"
                onClick={() => navigate(`/order-packers/${rec.id}`)}
                size="small"
              />
            )}
          />
        </Datagrid>
      </ReferenceManyField>
    </Box>
  );
};

export const ProgramEdit = () => (
  <Edit title={<ProgramTitle />}>
    <SimpleForm>
      <TextInput source="name" required />
      <SelectInput source="MeetingDay" choices={MEETING_DAY_CHOICES} required />
      <TextInput source="meeting_time" type="time" required />
      <TextInput source="meeting_address" multiline rows={2} required />
      <SelectInput
        source="default_split_strategy"
        choices={SPLIT_STRATEGY_CHOICES}
        helperText="Optional — choose 'None' if orders won't be split between packers"
      />
    </SimpleForm>
  </Edit>
);

export const ProgramCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" required />
      <SelectInput source="MeetingDay" choices={MEETING_DAY_CHOICES} required />
      <TextInput source="meeting_time" type="time" defaultValue="09:00" required />
      <TextInput source="meeting_address" multiline rows={2} required />
      <SelectInput
        source="default_split_strategy"
        choices={SPLIT_STRATEGY_CHOICES}
        defaultValue="none"
        helperText="Optional — choose 'None' if orders won't be split between packers"
      />
    </SimpleForm>
  </Create>
);
