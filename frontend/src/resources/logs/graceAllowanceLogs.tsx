/**
 * GraceAllowanceLog Resource — read-only audit trail of over-budget orders.
 * Mirrors GraceAllowanceLogAdmin from apps/log/admin.py
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  NumberField,
  Show,
  SimpleShowLayout,
  TopToolbar,
  ListButton,
  ShowButton,
  FilterButton,
  ExportButton,
  SearchInput,
  SelectInput,
} from 'react-admin';
import { ProceededChip } from './shared';

const PROCEEDED_CHOICES = [
  { id: 'true', name: 'Proceeded' },
  { id: 'false', name: 'Reviewed Only' },
];

const graceFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <SelectInput source="proceeded" choices={PROCEEDED_CHOICES} key="proceeded" />,
];

// ─── List ─────────────────────────────────────────────────────────────────────

export const GraceAllowanceLogList = () => (
  <List
    filters={graceFilters}
    sort={{ field: 'created_at', order: 'DESC' }}
    perPage={25}
    actions={
      <TopToolbar>
        <FilterButton />
        <ExportButton />
      </TopToolbar>
    }
  >
    <Datagrid rowClick="show" bulkActionButtons={false}>
      <DateField source="created_at" label="Date" showTime />
      <TextField source="participant_name" label="Participant" />
      <TextField source="participant_customer_number" label="Customer #" />
      <TextField source="order_number" label="Order" emptyText="—" />
      <NumberField
        source="amount_over"
        label="Amount Over"
        options={{ style: 'currency', currency: 'USD' }}
      />
      <ProceededChip />
      <ShowButton />
    </Datagrid>
  </List>
);

// ─── Show ─────────────────────────────────────────────────────────────────────

export const GraceAllowanceLogShow = () => (
  <Show
    actions={
      <TopToolbar>
        <ListButton />
      </TopToolbar>
    }
  >
    <SimpleShowLayout>
      <DateField source="created_at" label="Date" showTime />
      <TextField source="participant_name" label="Participant" />
      <TextField source="participant_customer_number" label="Customer #" />
      <TextField source="order_number" label="Order" emptyText="—" />
      <NumberField
        source="amount_over"
        label="Amount Over Budget"
        options={{ style: 'currency', currency: 'USD' }}
      />
      <ProceededChip />
      <TextField source="grace_message" label="Educational Message Shown" />
    </SimpleShowLayout>
  </Show>
);
