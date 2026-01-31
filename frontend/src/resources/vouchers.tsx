/**
 * Voucher Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  BooleanField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  BooleanInput,
  SelectInput,
  ReferenceInput,
  ReferenceField,
  Show,
  SimpleShowLayout,
  EditButton,
  ShowButton,
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
} from 'react-admin';
import { useState } from 'react';

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
    <CreateButton />
    <BulkCreateButton />
    <ExportButton />
  </TopToolbar>
);

// Bulk Create Button
const BulkCreateButton = () => {
  // This would open a modal for bulk voucher creation
  // For now, just a placeholder that links to a custom route
  return (
    <Button
      label="Bulk Create"
      onClick={() => {
        // Navigate to bulk create page or open modal
        window.location.href = '#/vouchers/bulk-create';
      }}
    />
  );
};

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

// Expire Voucher Button
const ExpireVoucherButton = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const dataProvider = useDataProvider();
  const [loading, setLoading] = useState(false);

  if (!record || record.state === 'consumed' || record.state === 'expired') return null;

  const handleExpire = async () => {
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

  return <Button label="Expire" onClick={handleExpire} disabled={loading} />;
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
        source="voucher_amnt"
        label="Amount"
        render={(record: { voucher_amnt: number }) =>
          record ? `$${Number(record.voucher_amnt).toFixed(2)}` : ''
        }
      />
      <BooleanField source="active" />
      <DateField source="created_at" label="Created" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

const VoucherTitle = () => {
  const record = useRecordContext();
  return <span>Voucher #{record?.id || ''}</span>;
};

export const VoucherShow = () => (
  <Show
    title={<VoucherTitle />}
    actions={
      <TopToolbar>
        <ApplyVoucherButton />
        <ExpireVoucherButton />
        <EditButton />
      </TopToolbar>
    }
  >
    <SimpleShowLayout>
      <TextField source="id" label="Voucher ID" />
      <ReferenceField source="account" reference="account-balances">
        <TextField source="participant_name" />
      </ReferenceField>
      <TextField source="participant_name" label="Participant" />
      <TextField source="participant_customer_number" label="Customer #" />
      <TextField source="program_name" label="Program" />
      <TextField source="voucher_type" label="Type" />
      <StateField />
      <FunctionField
        source="voucher_amnt"
        label="Amount"
        render={(record: { voucher_amnt: number }) =>
          record ? `$${Number(record.voucher_amnt).toFixed(2)}` : ''
        }
      />
      <BooleanField source="active" />
      <BooleanField source="program_pause_flag" label="Program Pause" />
      <TextField source="notes" />
      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />
    </SimpleShowLayout>
  </Show>
);

export const VoucherEdit = () => (
  <Edit title={<VoucherTitle />}>
    <SimpleForm>
      <ReferenceInput source="account" reference="account-balances" disabled>
        <SelectInput optionText="participant_name" />
      </ReferenceInput>
      <SelectInput source="voucher_type" choices={VOUCHER_TYPE_CHOICES} disabled />
      <BooleanInput source="active" />
      <BooleanInput source="program_pause_flag" label="Program Pause Flag" />
      <TextInput source="notes" multiline rows={3} />
    </SimpleForm>
  </Edit>
);

export const VoucherCreate = () => (
  <Create>
    <SimpleForm>
      <ReferenceInput source="account" reference="account-balances" required>
        <SelectInput optionText="participant_name" />
      </ReferenceInput>
      <SelectInput
        source="voucher_type"
        choices={VOUCHER_TYPE_CHOICES}
        defaultValue="grocery"
      />
      <BooleanInput source="program_pause_flag" label="Program Pause Flag" defaultValue={false} />
      <TextInput source="notes" multiline rows={3} />
    </SimpleForm>
  </Create>
);
