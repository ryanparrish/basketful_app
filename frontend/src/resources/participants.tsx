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
} from '@mui/material';
import PrintIcon from '@mui/icons-material/Print';
import { useNavigate } from 'react-router-dom';
import { API_URL } from '../utils/apiUrl';

const participantFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <BooleanInput source="active" label="Active Only" key="active" />,
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
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', p: 2, bgcolor: 'grey.50' }}>
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

interface ConfirmBulkButtonProps {
  label: string;
  endpoint: string;
  confirmTitle: string;
  confirmBody: string;
  color?: 'error' | 'warning' | 'primary';
}

const ConfirmBulkButton = ({
  label,
  endpoint,
  confirmTitle,
  confirmBody,
  color = 'primary',
}: ConfirmBulkButtonProps) => {
  const { selectedIds } = useListContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const unselectAll = useUnselectAll('participants');
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
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
      setOpen(false);
    }
  };

  return (
    <>
      <Button size="small" color={color} onClick={() => setOpen(true)}>
        {label}
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>{confirmTitle}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {confirmBody.replace('{count}', String(selectedIds.length))}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} color={color} variant="contained" disabled={loading}>
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

interface SimpleBulkButtonProps {
  label: string;
  endpoint: string;
}

const SimpleBulkButton = ({ label, endpoint }: SimpleBulkButtonProps) => {
  const { selectedIds } = useListContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const unselectAll = useUnselectAll('participants');
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
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
    }
  };

  return (
    <Button size="small" onClick={handleClick} disabled={loading}>
      {label}
    </Button>
  );
};

const PrintBulkButton = () => {
  const { selectedIds } = useListContext();
  const navigate = useNavigate();
  return (
    <Button
      size="small"
      startIcon={<PrintIcon />}
      onClick={() => navigate(`/participants/print-customer-list?ids=${selectedIds.join(',')}`)}
    >
      Print Customer List
    </Button>
  );
};

const ParticipantBulkActions = () => (
  <>
    <SimpleBulkButton label="Calculate Base Balance" endpoint="bulk-calculate-base-balance" />
    <SimpleBulkButton label="Resend Onboarding Email" endpoint="bulk-resend-onboarding" />
    <SimpleBulkButton label="Resend Password Reset Email" endpoint="bulk-resend-password-reset" />
    <ConfirmBulkButton
      label="Reset Password"
      endpoint="bulk-reset-password"
      confirmTitle="Reset passwords?"
      confirmBody="This will reset passwords and queue reset emails for {count} participant(s). Continue?"
      color="warning"
    />
    <ConfirmBulkButton
      label="Create User Accounts"
      endpoint="bulk-create-user-accounts"
      confirmTitle="Create user accounts?"
      confirmBody="This will create user accounts and send onboarding emails for {count} participant(s). Continue?"
    />
    <ConfirmBulkButton
      label="Create User Accounts (Silent)"
      endpoint="bulk-create-user-accounts-silent"
      confirmTitle="Create user accounts (silent)?"
      confirmBody="This will create user accounts (no email) for {count} participant(s). Continue?"
    />
    <PrintBulkButton />
  </>
);

// ── List ─────────────────────────────────────────────────────────────────────

export const ParticipantList = () => (
  <List filters={participantFilters} actions={<ListActions />} sort={{ field: 'name', order: 'ASC' }}>
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
      <BooleanField source="active" />
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

export const ParticipantShow = () => (
  <Show title={<ParticipantTitle />}>
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
