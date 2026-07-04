/**
 * Voucher Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  BooleanInput,
  SelectInput,
  Show,
  SimpleShowLayout,
  FilterButton,
  CreateButton,
  ExportButton,
  TopToolbar,
  SearchInput,
  useRecordContext,
  FunctionField,
  Button,
  useNotify,
  useRefresh,
  useDataProvider,
  useUpdate,
  useRedirect,
  Labeled,
} from 'react-admin';
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import MuiTextField from '@mui/material/TextField';
import MuiButton from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import EditIcon from '@mui/icons-material/Edit';
import { BackNavButton } from '../components/BackNavButton';

const VOUCHER_TYPE_CHOICES = [
  { id: 'grocery', name: 'Grocery' },
  { id: 'life', name: 'Life Skills' },
];

const STATE_CHOICES = [
  { id: 'pending', name: 'Pending' },
  { id: 'applied', name: 'Applied' },
  { id: 'consumed', name: 'Consumed' },
  { id: 'expired', name: 'Expired' },
];

const voucherFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <SelectInput source="state" choices={STATE_CHOICES} key="state" />,
  <SelectInput source="voucher_type" choices={VOUCHER_TYPE_CHOICES} key="type" />,
  <BooleanInput source="active" label="Active Only" key="active" />,
];

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <CreateButton label="Create Vouchers" />
    <BulkStatusUpdateButton />
    <ExportButton />
  </TopToolbar>
);

// Bulk Status Update Button
const BulkStatusUpdateButton = () => (
  <Button
    label="Bulk Status Update"
    onClick={() => {
      window.location.href = '#/vouchers/bulk-status-update';
    }}
  />
);

// State color mapping
const getStateColor = (state: string): string => {
  const colors: Record<string, string> = {
    pending: '#FFA726',
    applied: '#66BB6A',
    consumed: '#9E9E9E',
    expired: '#EF5350',
  };
  return colors[state] || '#9E9E9E';
};

const StateField = () => {
  const record = useRecordContext();
  if (!record) return null;
  return (
    <span
      style={{
        backgroundColor: getStateColor(record.state),
        color: 'white',
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '0.875rem',
      }}
    >
      {record.state.toUpperCase()}
    </span>
  );
};

const MultiplierChip = () => {
  const record = useRecordContext();
  if (!record || !record.program_pause_flag || record.multiplier <= 1) return null;
  const isExtended = record.multiplier >= 3;
  return (
    <span
      style={{
        backgroundColor: isExtended ? '#EF6C00' : '#F9A825',
        color: 'white',
        padding: '3px 8px',
        borderRadius: '4px',
        fontSize: '0.75rem',
        fontWeight: 600,
        letterSpacing: '0.5px',
      }}
    >
      {record.multiplier}× {isExtended ? 'EXTENDED PAUSE' : 'PAUSE'}
    </span>
  );
};

// Apply Voucher Button
const ApplyVoucherButton = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const dataProvider = useDataProvider();
  const [loading, setLoading] = useState(false);

  if (!record || record.state !== 'pending') return null;

  const handleApply = async () => {
    setLoading(true);
    try {
      await dataProvider.create(`vouchers/${record.id}/apply`, { data: {} });
      notify('Voucher applied successfully', { type: 'success' });
      refresh();
    } catch (error) {
      notify(`Error applying voucher: ${error}`, { type: 'error' });
    }
    setLoading(false);
  };

  return <Button label="Apply" onClick={handleApply} disabled={loading} />;
};

// Revert to Pending Button
const RevertToPendingButton = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const dataProvider = useDataProvider();
  const [loading, setLoading] = useState(false);

  if (!record || record.state !== 'applied') return null;

  const handleRevert = async () => {
    setLoading(true);
    try {
      await dataProvider.create(`vouchers/${record.id}/revert_to_pending`, { data: {} });
      notify('Voucher reverted to pending', { type: 'success' });
      refresh();
    } catch (error) {
      notify(`Error reverting voucher: ${error}`, { type: 'error' });
    }
    setLoading(false);
  };

  return <Button label="Mark as Pending" onClick={handleRevert} disabled={loading} />;
};

// Expire Voucher Button
const ExpireVoucherButton = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const dataProvider = useDataProvider();
  const [loading, setLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  if (!record || record.state === 'consumed' || record.state === 'expired') return null;

  const handleExpire = async () => {
    setConfirmOpen(false);
    setLoading(true);
    try {
      await dataProvider.create(`vouchers/${record.id}/expire`, { data: {} });
      notify('Voucher expired', { type: 'info' });
      refresh();
    } catch (error) {
      notify(`Error expiring voucher: ${error}`, { type: 'error' });
    }
    setLoading(false);
  };

  return (
    <>
      <Button
        label="Expire"
        onClick={() => setConfirmOpen(true)}
        disabled={loading}
        sx={{ color: '#d32f2f' }}
      />
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <DialogTitle>Expire this voucher?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will permanently expire the voucher. This <strong>cannot be undone</strong>.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <MuiButton onClick={() => setConfirmOpen(false)}>Cancel</MuiButton>
          <MuiButton onClick={handleExpire} color="error" variant="contained">
            Expire
          </MuiButton>
        </DialogActions>
      </Dialog>
    </>
  );
};

// Inline Active Toggle
const InlineActiveToggle = () => {
  const record = useRecordContext();
  const [update, { isPending }] = useUpdate();
  const notify = useNotify();
  if (!record) return null;

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    try {
      await update('vouchers', { id: record.id, data: { active: e.target.checked }, previousData: record });
      notify(e.target.checked ? 'Voucher activated' : 'Voucher deactivated', { type: 'success' });
    } catch {
      notify('Error updating voucher', { type: 'error' });
    }
  };

  return (
    <FormControlLabel
      control={
        <Switch
          checked={!!record.active}
          onChange={handleChange}
          disabled={isPending}
          size="small"
        />
      }
      label={record.active ? 'Active' : 'Inactive'}
      sx={{ m: 0 }}
    />
  );
};

// Inline Notes Editor
const InlineNotesEditor = () => {
  const record = useRecordContext();
  const [update, { isPending }] = useUpdate();
  const notify = useNotify();
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState('');

  useEffect(() => {
    setNotes(record?.notes ?? '');
  }, [record?.notes]);

  if (!record) return null;

  const handleSave = async () => {
    try {
      await update('vouchers', { id: record.id, data: { notes }, previousData: record });
      notify('Notes saved', { type: 'success' });
      setEditing(false);
    } catch {
      notify('Error saving notes', { type: 'error' });
    }
  };

  if (editing) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, pt: 0.5 }}>
        <MuiTextField
          multiline
          rows={3}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          size="small"
          fullWidth
          autoFocus
        />
        <Box sx={{ display: 'flex', gap: 1 }}>
          <MuiButton size="small" variant="contained" onClick={handleSave} disabled={isPending}>
            Save
          </MuiButton>
          <MuiButton
            size="small"
            onClick={() => { setNotes(record.notes ?? ''); setEditing(false); }}
          >
            Cancel
          </MuiButton>
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5, minHeight: 24 }}>
      <span style={{ color: record.notes ? 'inherit' : '#9e9e9e' }}>
        {record.notes || 'No notes'}
      </span>
      <IconButton size="small" onClick={() => setEditing(true)} sx={{ mt: '-2px' }}>
        <EditIcon sx={{ fontSize: 14 }} />
      </IconButton>
    </Box>
  );
};

// With Pause field — only renders when a pause multiplier is active
const WithPauseField = () => {
  const record = useRecordContext();
  if (!record?.program_pause_flag || record.multiplier <= 1) return null;
  const effective = Number(record.voucher_amnt) * record.multiplier;
  return (
    <FunctionField
      label="Effective Amount (with pause)"
      render={() => (
        <span style={{ color: '#F9A825', fontWeight: 600 }}>${effective.toFixed(2)}</span>
      )}
    />
  );
};

export const VoucherList = () => (
  <List
    filters={voucherFilters}
    actions={<ListActions />}
    sort={{ field: 'created_at', order: 'DESC' }}
  >
    <Datagrid rowClick="show">
      <TextField source="id" label="ID" />
      <TextField source="participant_name" label="Participant" />
      <TextField source="voucher_type" label="Type" />
      <StateField />
      <FunctionField
        label="Multiplier"
        render={(record: { program_pause_flag: boolean; multiplier: number }) =>
          record?.program_pause_flag && record.multiplier > 1 ? (
            <span
              style={{
                backgroundColor: record.multiplier >= 3 ? '#EF6C00' : '#F9A825',
                color: 'white',
                padding: '3px 8px',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontWeight: 600,
              }}
            >
              {record.multiplier}×
            </span>
          ) : null
        }
      />
      <FunctionField
        source="voucher_amnt"
        label="Amount"
        render={(record: { voucher_amnt: number }) =>
          record ? `$${Number(record.voucher_amnt).toFixed(2)}` : ''
        }
      />
      <DateField source="created_at" label="Created" />
    </Datagrid>
  </List>
);

const VoucherTitle = () => {
  const record = useRecordContext();
  return <span>Voucher #{record?.id || ''}</span>;
};

function VoucherShowActions() {
  return (
    <TopToolbar sx={{ alignItems: 'center' }}>
      <BackNavButton to="/vouchers" label="All Vouchers" />
      <ApplyVoucherButton />
      <RevertToPendingButton />
      <ExpireVoucherButton />
    </TopToolbar>
  );
}

export const VoucherShow = () => (
  <Show
    title={<VoucherTitle />}
    actions={<VoucherShowActions />}
  >
    <SimpleShowLayout>
      <TextField source="participant_name" label="Participant" />
      <TextField source="participant_customer_number" label="Customer #" />
      <TextField source="program_name" label="Program" />
      <TextField source="voucher_type" label="Type" />
      <StateField />
      <MultiplierChip />
      <FunctionField
        label="Base Amount"
        render={(record: { voucher_amnt: number }) =>
          record ? `$${Number(record.voucher_amnt).toFixed(2)}` : ''
        }
      />
      <WithPauseField />
      <Labeled label="Available for Orders">
        <InlineActiveToggle />
      </Labeled>
      <Labeled label="Notes">
        <InlineNotesEditor />
      </Labeled>
      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />
    </SimpleShowLayout>
  </Show>
);

// VoucherEdit redirects to Show — all editing is inline on the Show screen
export const VoucherEdit = () => {
  const { id } = useParams();
  const redirect = useRedirect();
  useEffect(() => {
    if (id) redirect('show', 'vouchers', id);
  }, [id, redirect]);
  return null;
};

export const VoucherCreate = () => {
  const redirect = useRedirect();
  
  // Redirect to bulk create with select mode
  useEffect(() => {
    redirect('/vouchers/bulk-create?mode=select');
  }, [redirect]);
  
  return null;
};
