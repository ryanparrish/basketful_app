/**
 * Participant Resource Components
 */
import { useState } from 'react';
import {
  List,
  Datagrid,
  TextField,
  EmailField,
  BooleanField,
  DateField,
  NumberField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  BooleanInput,
  NumberInput,
  ReferenceInput,
  SelectInput,
  ReferenceField,
  Show,
  EditButton,
  ShowButton,
  FilterButton,
  CreateButton,
  ExportButton,
  TopToolbar,
  SearchInput,
  useRecordContext,
  useNotify,
  useRefresh,
  useUnselectAll,
  TabbedShowLayout,
  ReferenceManyField,
  FunctionField,
  Labeled,
  useListContext,
  type RaRecord,
} from 'react-admin';
import {
  Typography,
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Chip,
  FormControlLabel,
  Switch,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  ButtonGroup,
} from '@mui/material';
import PrintIcon from '@mui/icons-material/Print';
import ArchiveIcon from '@mui/icons-material/Archive';
import RestoreIcon from '@mui/icons-material/Restore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import LockResetIcon from '@mui/icons-material/LockReset';
import EmailIcon from '@mui/icons-material/Email';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import CalculateIcon from '@mui/icons-material/Calculate';
import { useNavigate } from 'react-router-dom';
import { API_URL } from '../utils/apiUrl';

const participantFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <ReferenceInput source="program" reference="programs" key="program">
    <SelectInput optionText="name" />
  </ReferenceInput>,
];

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <CreateButton />
    <ExportButton />
  </TopToolbar>
);

// ── Balance expand panel ──────────────────────────────────────────────────────

const BalanceExpandPanel = () => {
  const record = useRecordContext();
  if (!record) return null;
  const b = record.balances ?? {};
  const fmt = (v: unknown) =>
    v !== undefined && v !== null ? `$${Number(v).toFixed(2)}` : '—';

  const items = [
    { label: 'Full Balance', value: fmt(b.full_balance) },
    { label: 'Available', value: fmt(b.available_balance) },
    { label: 'Hygiene', value: fmt(b.hygiene_balance) },
    { label: 'Go Fresh', value: fmt(b.go_fresh_balance) },
    { label: 'Base Balance', value: fmt(record.base_balance) },
  ];

  return (
    <Box sx={{ 
      display: 'flex', 
      gap: 2, 
      flexWrap: 'wrap', 
      p: 2, 
      bgcolor: (theme) => theme.palette.mode === 'dark'
        ? 'rgba(255, 255, 255, 0.03)'
        : 'grey.50'
    }}>
      {items.map(({ label, value }) => (
        <Box
          key={label}
          sx={{
            px: 2,
            py: 1.5,
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            minWidth: 130,
            textAlign: 'center',
          }}
        >
          <Typography variant="caption" color="text.secondary" display="block">
            {label}
          </Typography>
          <Typography variant="subtitle1" fontWeight="bold">
            {value}
          </Typography>
        </Box>
      ))}
    </Box>
  );
};

// ── Bulk action helpers ───────────────────────────────────────────────────────

async function callBulkAction(endpoint: string, ids: (string | number)[]): Promise<string> {
  const token = localStorage.getItem('accessToken');
  const res = await fetch(`${API_URL}/api/v1/participants/${endpoint}/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ ids }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || data?.message || 'Action failed');
  return data.message ?? 'Done.';
}


const ParticipantBulkActions = () => {
  const { selectedIds, data = [] } = useListContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const unselectAll = useUnselectAll('participants');
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [dialogState, setDialogState] = useState<{
    open: boolean;
    action: string;
    title: string;
    body: string;
    color: 'error' | 'warning' | 'success' | 'primary';
    endpoint: string;
  }>({ open: false, action: '', title: '', body: '', color: 'primary', endpoint: '' });
  const [loading, setLoading] = useState(false);

  // Determine if selection has archived or active participants
  const selectedRecords = data.filter((record: RaRecord) => 
    selectedIds.includes(record.id)
  );
  const hasActiveSelected = selectedRecords.some((r: RaRecord) => r.active);
  const hasArchivedSelected = selectedRecords.some((r: RaRecord) => !r.active);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleAction = async (endpoint: string, requiresConfirm = false, config?: typeof dialogState) => {
    if (requiresConfirm && config) {
      setDialogState({ ...config, open: true });
      handleMenuClose();
      return;
    }

    setLoading(true);
    try {
      const msg = await callBulkAction(endpoint, selectedIds);
      notify(msg, { type: 'success' });
      refresh();
      unselectAll();
    } catch (e) {
      notify((e as Error).message, { type: 'error' });
    } finally {
      setLoading(false);
      handleMenuClose();
    }
  };

  const handleConfirmAction = async () => {
    setLoading(true);
    try {
      const msg = await callBulkAction(dialogState.endpoint, selectedIds);
      notify(msg, { type: 'success' });
      refresh();
      unselectAll();
    } catch (e) {
      notify((e as Error).message, { type: 'error' });
    } finally {
      setLoading(false);
      setDialogState({ ...dialogState, open: false });
    }
  };

  return (
    <Box sx={{ 
      display: 'flex', 
      alignItems: 'center', 
      gap: 1, 
      flexWrap: 'wrap',
      p: 2,
      bgcolor: (theme) => theme.palette.mode === 'dark'
        ? 'rgba(144, 202, 249, 0.08)'  // Light blue tint for dark mode
        : 'rgba(25, 118, 210, 0.08)',   // Light blue tint for light mode
      borderBottom: 1,
      borderColor: (theme) => theme.palette.mode === 'dark'
        ? 'rgba(144, 202, 249, 0.16)'
        : 'rgba(25, 118, 210, 0.16)',
    }}>
      {/* Selection count badge */}
      <Chip 
        label={`${selectedIds.length} selected`}
        size="small"
        sx={{
          bgcolor: (theme) => theme.palette.mode === 'dark' 
            ? 'primary.dark' 
            : 'primary.light',
          color: (theme) => theme.palette.mode === 'dark'
            ? 'primary.contrastText'
            : 'primary.dark',
          fontWeight: 600
        }}
      />

      {/* PRIMARY ACTIONS - Archive/Restore (60% of usage) */}
      <ButtonGroup variant="contained" size="small">
        {hasActiveSelected && (
          <Button
            startIcon={<ArchiveIcon />}
            onClick={() => handleAction('bulk-archive', true, {
              open: true,
              action: 'archive',
              title: 'Archive Participants?',
              body: `This will archive ${selectedIds.length} participant(s) and hide them from the active list. They can be restored later.`,
              color: 'warning',
              endpoint: 'bulk-archive'
            })}
            color="warning"
            disabled={loading}
          >
            Archive
          </Button>
        )}
        {hasArchivedSelected && (
          <Button
            startIcon={<RestoreIcon />}
            onClick={() => handleAction('bulk-unarchive', true, {
              open: true,
              action: 'restore',
              title: 'Restore Participants?',
              body: `This will restore ${selectedIds.length} participant(s) to active status.`,
              color: 'success',
              endpoint: 'bulk-unarchive'
            })}
            color="success"
            disabled={loading}
          >
            Restore
          </Button>
        )}
      </ButtonGroup>

      {/* SECONDARY ACTION - Reset Password (20% of usage) */}
      <Button
        variant="outlined"
        size="small"
        startIcon={<LockResetIcon />}
        onClick={() => handleAction('bulk-reset-password', true, {
          open: true,
          action: 'reset-password',
          title: 'Reset passwords?',
          body: `This will reset passwords and queue reset emails for ${selectedIds.length} participant(s). Continue?`,
          color: 'warning',
          endpoint: 'bulk-reset-password'
        })}
        disabled={loading}
      >
        Reset Password
      </Button>

      {/* TERTIARY ACTIONS - More menu (20% of usage combined) */}
      <IconButton 
        size="small"
        onClick={handleMenuOpen}
        disabled={loading}
        sx={{ 
          border: 1,
          borderColor: 'divider',
          '&:hover': {
            bgcolor: 'action.hover'
          }
        }}
      >
        <MoreVertIcon fontSize="small" />
      </IconButton>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: { minWidth: 240 }
        }}
      >
        {/* Communication */}
        <MenuItem disabled sx={{ opacity: 0.6, fontSize: '0.75rem', fontWeight: 600 }}>
          Communication
        </MenuItem>
        <MenuItem onClick={() => handleAction('bulk-resend-onboarding')} sx={{ pl: 3 }}>
          <ListItemIcon>
            <EmailIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Resend Onboarding Email</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleAction('bulk-resend-password-reset')} sx={{ pl: 3 }}>
          <ListItemIcon>
            <EmailIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Resend Password Reset Email</ListItemText>
        </MenuItem>

        <Divider />

        {/* Account Management */}
        <MenuItem disabled sx={{ opacity: 0.6, fontSize: '0.75rem', fontWeight: 600 }}>
          Account Management
        </MenuItem>
        <MenuItem 
          onClick={() => handleAction('bulk-create-user-accounts', true, {
            open: true,
            action: 'create-accounts',
            title: 'Create user accounts?',
            body: `This will create user accounts and send onboarding emails for ${selectedIds.length} participant(s). Continue?`,
            color: 'primary',
            endpoint: 'bulk-create-user-accounts'
          })} 
          sx={{ pl: 3 }}
        >
          <ListItemIcon>
            <PersonAddIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Create User Accounts</ListItemText>
        </MenuItem>
        <MenuItem 
          onClick={() => handleAction('bulk-create-user-accounts-silent', true, {
            open: true,
            action: 'create-accounts-silent',
            title: 'Create user accounts (silent)?',
            body: `This will create user accounts (no email) for ${selectedIds.length} participant(s). Continue?`,
            color: 'primary',
            endpoint: 'bulk-create-user-accounts-silent'
          })} 
          sx={{ pl: 3 }}
        >
          <ListItemIcon>
            <PersonAddIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Create Accounts (Silent)</ListItemText>
        </MenuItem>

        <Divider />

        {/* Financial */}
        <MenuItem disabled sx={{ opacity: 0.6, fontSize: '0.75rem', fontWeight: 600 }}>
          Financial
        </MenuItem>
        <MenuItem onClick={() => handleAction('bulk-calculate-base-balance')} sx={{ pl: 3 }}>
          <ListItemIcon>
            <CalculateIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Calculate Base Balance</ListItemText>
        </MenuItem>

        <Divider />

        {/* Export */}
        <MenuItem 
          onClick={() => {
            navigate(`/participants/print-customer-list?ids=${selectedIds.join(',')}`);
            handleMenuClose();
          }} 
          sx={{ pl: 3 }}
        >
          <ListItemIcon>
            <PrintIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText>Print Customer List</ListItemText>
        </MenuItem>
      </Menu>

      {/* Confirmation Dialog */}
      <Dialog open={dialogState.open} onClose={() => setDialogState({ ...dialogState, open: false })}>
        <DialogTitle>{dialogState.title}</DialogTitle>
        <DialogContent>
          <DialogContentText>{dialogState.body}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogState({ ...dialogState, open: false })} disabled={loading}>
            Cancel
          </Button>
          <Button 
            onClick={handleConfirmAction} 
            color={dialogState.color} 
            variant="contained" 
            disabled={loading}
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ── List ─────────────────────────────────────────────────────────────────────

const ShowArchivedToggle = () => {
  const { filterValues, setFilters } = useListContext();
  const showArchived = !filterValues.active;

  return (
    <Box sx={{ 
      mb: 2, 
      p: 2, 
      bgcolor: (theme) => theme.palette.mode === 'dark'
        ? 'rgba(255, 255, 255, 0.05)'
        : 'grey.50',
      borderRadius: 1,
      border: 1,
      borderColor: (theme) => theme.palette.mode === 'dark'
        ? 'rgba(255, 255, 255, 0.12)'
        : 'grey.200',
    }}>
      <FormControlLabel
        control={
          <Switch
            checked={showArchived}
            onChange={(e) => {
              setFilters(
                { ...filterValues, active: e.target.checked ? undefined : true },
                {},
                false
              );
            }}
          />
        }
        label="Show Archived Participants"
      />
      <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
        (Archived participants are hidden by default)
      </Typography>
    </Box>
  );
};

export const ParticipantList = () => (
  <List
    filters={participantFilters}
    filterDefaultValues={{ active: true }}
    actions={<ListActions />}
    sort={{ field: 'name', order: 'ASC' }}
  >
    <ShowArchivedToggle />
    <Datagrid
      rowClick="show"
      expand={<BalanceExpandPanel />}
      expandSingle
      bulkActionButtons={<ParticipantBulkActions />}
    >
      <TextField source="customer_number" label="Customer #" />
      <TextField source="name" />
      <EmailField source="email" />
      <ReferenceField source="program" reference="programs" link="show">
        <TextField source="name" />
      </ReferenceField>
      <FunctionField
        label="Status"
        render={(record: RaRecord) => (
          <Chip
            label={record.active ? 'Active' : 'Archived'}
            size="small"
            icon={record.active ? <CheckCircleIcon /> : <ArchiveIcon />}
            sx={{
              fontWeight: 500,
              ...(record.active ? {
                bgcolor: (theme) => theme.palette.mode === 'dark' 
                  ? 'rgba(46, 125, 50, 0.2)' 
                  : 'success.light',
                color: (theme) => theme.palette.mode === 'dark'
                  ? '#81c784'
                  : 'success.dark',
              } : {
                bgcolor: (theme) => theme.palette.mode === 'dark' 
                  ? 'rgba(158, 158, 158, 0.2)' 
                  : 'grey.300',
                color: (theme) => theme.palette.mode === 'dark'
                  ? '#bdbdbd'
                  : 'grey.700',
              })
            }}
          />
        )}
        sortable={false}
      />
      <NumberField source="adults" />
      <NumberField source="children" />
      <DateField source="created_at" label="Joined" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

const ParticipantTitle = () => {
  const record = useRecordContext();
  return <span>Participant: {record?.name || ''}</span>;
};

const ParticipantShowActions = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [action, setAction] = useState<'archive' | 'unarchive'>('archive');

  const handleAction = async () => {
    if (!record) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(
        `${API_URL}/api/v1/participants/${record.id}/${action}/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Token ${token}`,
          },
        }
      );
      
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Action failed');
      }
      
      notify(
        `Participant ${action === 'archive' ? 'archived' : 'restored'} successfully`,
        { type: 'success' }
      );
      refresh();
    } catch (e) {
      notify((e as Error).message, { type: 'error' });
    } finally {
      setLoading(false);
      setDialogOpen(false);
    }
  };

  if (!record) return null;

  return (
    <TopToolbar>
      <EditButton />
      {record.active ? (
        <Button
          color="warning"
          startIcon={<ArchiveIcon />}
          onClick={() => {
            setAction('archive');
            setDialogOpen(true);
          }}
          disabled={loading}
        >
          Archive
        </Button>
      ) : (
        <Button
          color="success"
          startIcon={<RestoreIcon />}
          onClick={() => {
            setAction('unarchive');
            setDialogOpen(true);
          }}
          disabled={loading}
        >
          Restore
        </Button>
      )}
      
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
        <DialogTitle>
          {action === 'archive' ? 'Archive' : 'Restore'} Participant?
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            {action === 'archive'
              ? 'This will archive the participant and hide them from the active list. They can be restored later.'
              : 'This will restore the participant to active status.'}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={handleAction}
            color={action === 'archive' ? 'warning' : 'success'}
            variant="contained"
            disabled={loading}
          >
            {action === 'archive' ? 'Archive' : 'Restore'}
          </Button>
        </DialogActions>
      </Dialog>
    </TopToolbar>
  );
};

export const ParticipantShow = () => (
  <Show title={<ParticipantTitle />} actions={<ParticipantShowActions />}>
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Details">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', mb: 2 }}>
              Basic Information
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField source="customer_number" label="Customer Number" />
              <TextField source="name" label="Name" />
              <EmailField source="email" label="Email" />
              <TextField source="phone_number" label="Phone" />
            </Box>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', mb: 2 }}>
              Program & Status
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <ReferenceField source="program" reference="programs" label="Program">
                <TextField source="name" />
              </ReferenceField>
              <BooleanField source="active" label="Active" />
              <FunctionField
                label="Archive Status"
                render={(record: RaRecord) => {
                  if (record.active) {
                    return <Typography variant="body2" color="text.secondary">Active</Typography>;
                  }
                  if (record.archived_at) {
                    const date = new Date(record.archived_at);
                    return (
                      <Typography variant="body2" color="text.secondary">
                        Archived on {date.toLocaleDateString()} at {date.toLocaleTimeString()}
                      </Typography>
                    );
                  }
                  return <Typography variant="body2" color="text.secondary">Archived</Typography>;
                }}
              />
              <DateField source="created_at" label="Created at" showTime />
              <DateField source="updated_at" label="Updated at" showTime />
            </Box>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', mb: 2 }}>
              Household Size
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Labeled label="Adults">
                <NumberField source="adults" />
              </Labeled>
              <Labeled label="Children">
                <NumberField source="children" />
              </Labeled>
              <Labeled label="Infants">
                <NumberField source="infants" />
              </Labeled>
            </Box>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', mb: 2 }}>
              Additional Information
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField source="dietary_restrictions" label="Dietary Restrictions" />
            </Box>
          </Box>
        </Box>
      </TabbedShowLayout.Tab>
      
      <TabbedShowLayout.Tab label="Vouchers" path="vouchers">
        <ReferenceManyField
          reference="vouchers"
          target="participant"
          label="Recent Vouchers"
          sort={{ field: 'created_at', order: 'DESC' }}
          perPage={10}
        >
          <Datagrid rowClick="show">
            <TextField source="id" label="Voucher #" />
            <DateField source="created_at" label="Created" />
            <FunctionField
              label="Type"
              render={(record: RaRecord) =>
                record.voucher_type === 'grocery' ? 'Grocery' : 'Life Skills'
              }
            />
            <NumberField
              source="voucher_amnt"
              label="Amount"
              options={{ style: 'currency', currency: 'USD' }}
            />
            <FunctionField
              label="Status"
              render={(record: RaRecord) => {
                const stateLabels: Record<string, string> = {
                  pending: 'Pending',
                  applied: 'Applied',
                  consumed: 'Consumed',
                  expired: 'Expired',
                };
                return stateLabels[record.state] ?? record.state;
              }}
            />
            <ShowButton />
          </Datagrid>
        </ReferenceManyField>
      </TabbedShowLayout.Tab>
      
      <TabbedShowLayout.Tab label="Orders" path="orders">
        <ReferenceManyField 
          reference="orders" 
          target="participant"
          label="Recent Orders"
          sort={{ field: 'created_at', order: 'DESC' }}
          perPage={10}
        >
          <Datagrid rowClick="show">
            <TextField source="order_number" label="Order #" />
            <DateField source="created_at" label="Order Date" showTime />
            <ReferenceField source="voucher" reference="vouchers" link="show">
              <TextField source="voucher_number" />
            </ReferenceField>
            <FunctionField 
              label="Items" 
              render={(record: RaRecord) => record.items?.length || 0}
            />
            <DateField source="pickup_date" label="Pickup Date" />
            <ShowButton />
          </Datagrid>
        </ReferenceManyField>
      </TabbedShowLayout.Tab>

      <TabbedShowLayout.Tab label="Balances" path="balances">
        <FunctionField
          render={(record: RaRecord) => {
            const b = record?.balances ?? {};
            const fmt = (v: unknown) =>
              v !== undefined && v !== null ? `$${Number(v).toFixed(2)}` : '—';
            const items = [
              { label: 'Full Balance', value: fmt(b.full_balance), description: 'Total balance including all vouchers' },
              { label: 'Available Balance', value: fmt(b.available_balance), description: 'Balance available for grocery orders' },
              { label: 'Hygiene Balance', value: fmt(b.hygiene_balance), description: 'Balance available for hygiene products' },
              { label: 'Go Fresh Balance', value: fmt(b.go_fresh_balance), description: 'Per-order Go Fresh budget' },
              { label: 'Base Balance', value: fmt(record?.base_balance), description: 'Calculated base balance from AccountBalance' },
            ];
            return (
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 1 }}>
                {items.map(({ label, value, description }) => (
                  <Box
                    key={label}
                    sx={{
                      px: 3, py: 2,
                      bgcolor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 2,
                      minWidth: 180,
                    }}
                  >
                    <Typography variant="caption" color="text.secondary" display="block">
                      {label}
                    </Typography>
                    <Typography variant="h5" fontWeight="bold" sx={{ my: 0.5 }}>
                      {value}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {description}
                    </Typography>
                  </Box>
                ))}
              </Box>
            );
          }}
        />
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

export const ParticipantEdit = () => (
  <Edit title={<ParticipantTitle />}>
    <SimpleForm>
      <TextInput source="name" required />
      <TextInput source="email" type="email" />
      <TextInput source="phone_number" label="Phone Number" />
      <ReferenceInput source="program" reference="programs">
        <SelectInput optionText="name" />
      </ReferenceInput>
      <BooleanInput source="active" />
      <NumberInput source="adults" min={0} />
      <NumberInput source="children" min={0} />
      <NumberInput source="infants" min={0} />
      <TextInput source="dietary_restrictions" multiline rows={3} />
    </SimpleForm>
  </Edit>
);

export const ParticipantCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" required />
      <TextInput source="email" type="email" />
      <TextInput source="phone_number" label="Phone Number" />
      <ReferenceInput source="program" reference="programs" required>
        <SelectInput optionText="name" />
      </ReferenceInput>
      <BooleanInput source="active" defaultValue={true} />
      <NumberInput source="adults" min={0} defaultValue={1} />
      <NumberInput source="children" min={0} defaultValue={0} />
      <NumberInput source="infants" min={0} defaultValue={0} />
      <TextInput source="dietary_restrictions" multiline rows={3} />
    </SimpleForm>
  </Create>
);
