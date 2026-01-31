/**
 * Order Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  NumberField,
  BooleanField,
  Edit,
  Create,
  SimpleForm,
  SelectInput,
  ReferenceInput,
  ReferenceField,
  Show,
  TabbedShowLayout,
  EditButton,
  ShowButton,
  FilterButton,
  ExportButton,
  TopToolbar,
  SearchInput,
  useRecordContext,
  ArrayField,
  SingleFieldList,
  ChipField,
  FunctionField,
  Button,
  useUpdate,
  useNotify,
  useRefresh,
  Confirm,
} from 'react-admin';
import { useState } from 'react';

const STATUS_CHOICES = [
  { id: 'pending', name: 'Pending' },
  { id: 'confirmed', name: 'Confirmed' },
  { id: 'packing', name: 'Packing' },
  { id: 'completed', name: 'Completed' },
  { id: 'cancelled', name: 'Cancelled' },
];

const orderFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <SelectInput source="status" choices={STATUS_CHOICES} key="status" />,
  <ReferenceInput source="account" reference="account-balances" key="account">
    <SelectInput optionText="participant_name" />
  </ReferenceInput>,
];

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <ExportButton />
  </TopToolbar>
);

// Status color mapping
const getStatusColor = (status: string): string => {
  const colors: Record<string, string> = {
    pending: '#FFA726',
    confirmed: '#66BB6A',
    packing: '#42A5F5',
    completed: '#4CAF50',
    cancelled: '#EF5350',
  };
  return colors[status] || '#9E9E9E';
};

const StatusField = () => {
  const record = useRecordContext();
  if (!record) return null;
  return (
    <span
      style={{
        backgroundColor: getStatusColor(record.status),
        color: 'white',
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '0.875rem',
      }}
    >
      {record.status.toUpperCase()}
    </span>
  );
};

export const OrderList = () => (
  <List
    filters={orderFilters}
    actions={<ListActions />}
    sort={{ field: 'order_date', order: 'DESC' }}
  >
    <Datagrid rowClick="show">
      <TextField source="order_number" label="Order #" />
      <TextField source="participant_name" label="Participant" />
      <TextField source="participant_customer_number" label="Customer #" />
      <StatusField />
      <FunctionField
        source="total_price"
        label="Total"
        render={(record: { total_price: number }) =>
          record ? `$${Number(record.total_price).toFixed(2)}` : ''
        }
      />
      <NumberField source="item_count" label="Items" />
      <BooleanField source="paid" />
      <DateField source="order_date" showTime />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

const OrderTitle = () => {
  const record = useRecordContext();
  return <span>Order: {record?.order_number || ''}</span>;
};

// Confirm Order Button Component
const ConfirmOrderButton = () => {
  const record = useRecordContext();
  const [open, setOpen] = useState(false);
  const notify = useNotify();
  const refresh = useRefresh();
  const [update, { isPending }] = useUpdate();

  if (!record || record.status !== 'pending') return null;

  const handleConfirm = () => {
    update(
      'orders',
      { id: record.id, data: { status: 'confirmed' }, previousData: record },
      {
        onSuccess: () => {
          notify('Order confirmed successfully', { type: 'success' });
          refresh();
        },
        onError: (error: Error) => {
          notify(`Error: ${error.message}`, { type: 'error' });
        },
      }
    );
    setOpen(false);
  };

  return (
    <>
      <Button
        label="Confirm Order"
        onClick={() => setOpen(true)}
        disabled={isPending}
      />
      <Confirm
        isOpen={open}
        title="Confirm Order"
        content="Are you sure you want to confirm this order? This will consume vouchers."
        onConfirm={handleConfirm}
        onClose={() => setOpen(false)}
      />
    </>
  );
};

// Cancel Order Button Component
const CancelOrderButton = () => {
  const record = useRecordContext();
  const [open, setOpen] = useState(false);
  const notify = useNotify();
  const refresh = useRefresh();
  const [update, { isPending }] = useUpdate();

  if (!record || ['completed', 'cancelled'].includes(record.status)) return null;

  const handleCancel = () => {
    update(
      'orders',
      { id: record.id, data: { status: 'cancelled' }, previousData: record },
      {
        onSuccess: () => {
          notify('Order cancelled', { type: 'info' });
          refresh();
        },
        onError: (error: Error) => {
          notify(`Error: ${error.message}`, { type: 'error' });
        },
      }
    );
    setOpen(false);
  };

  return (
    <>
      <Button label="Cancel Order" onClick={() => setOpen(true)} disabled={isPending} />
      <Confirm
        isOpen={open}
        title="Cancel Order"
        content="Are you sure you want to cancel this order?"
        onConfirm={handleCancel}
        onClose={() => setOpen(false)}
      />
    </>
  );
};

export const OrderShow = () => (
  <Show title={<OrderTitle />} actions={
    <TopToolbar>
      <ConfirmOrderButton />
      <CancelOrderButton />
      <EditButton />
    </TopToolbar>
  }>
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Summary">
        <TextField source="order_number" label="Order Number" />
        <StatusField />
        <TextField source="participant_name" label="Participant" />
        <TextField source="participant_customer_number" label="Customer #" />
        <TextField source="program_name" label="Program" />
        <FunctionField
          source="total_price"
          label="Total Price"
          render={(record: { total_price: number }) =>
            record ? `$${Number(record.total_price).toFixed(2)}` : ''
          }
        />
        <FunctionField
          source="go_fresh_total"
          label="Go Fresh Total"
          render={(record: { go_fresh_total: number }) =>
            record ? `$${Number(record.go_fresh_total).toFixed(2)}` : ''
          }
        />
        <BooleanField source="paid" />
        <BooleanField source="is_combined" label="In Combined Order" />
        <DateField source="order_date" showTime />
        <DateField source="created_at" showTime label="Created" />
        <DateField source="updated_at" showTime label="Last Updated" />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Items">
        <ArrayField source="items">
          <Datagrid bulkActionButtons={false}>
            <TextField source="product_name" label="Product" />
            <TextField source="product_category" label="Category" />
            <NumberField source="quantity" />
            <FunctionField
              source="price"
              label="Unit Price"
              render={(record: { price: number }) =>
                record ? `$${Number(record.price).toFixed(2)}` : ''
              }
            />
            <FunctionField
              source="total"
              label="Total"
              render={(record: { total: number }) =>
                record ? `$${Number(record.total).toFixed(2)}` : ''
              }
            />
          </Datagrid>
        </ArrayField>
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Validation Logs">
        <ArrayField source="validation_logs">
          <Datagrid bulkActionButtons={false}>
            <TextField source="error_message" />
            <DateField source="created_at" showTime />
          </Datagrid>
        </ArrayField>
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

export const OrderEdit = () => (
  <Edit title={<OrderTitle />}>
    <SimpleForm>
      <TextField source="order_number" />
      <SelectInput source="status" choices={STATUS_CHOICES} />
      <ReferenceInput source="account" reference="account-balances">
        <SelectInput optionText="participant_name" disabled />
      </ReferenceInput>
    </SimpleForm>
  </Edit>
);

export const OrderCreate = () => (
  <Create>
    <SimpleForm>
      <ReferenceInput source="account" reference="account-balances" required>
        <SelectInput optionText="participant_name" />
      </ReferenceInput>
    </SimpleForm>
  </Create>
);
