/**
 * OrderValidationLog Resource — read-only audit trail of order validation events.
 * Mirrors OrderValidationLog in apps/log/models.py
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
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
import { LogTypeBadge } from './shared';

const LOG_TYPE_CHOICES = [
  { id: 'INFO', name: 'Info' },
  { id: 'WARNING', name: 'Warning' },
  { id: 'ERROR', name: 'Error' },
];

const validationLogFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <SelectInput source="log_type" choices={LOG_TYPE_CHOICES} key="log_type" />,
];

// ─── List ─────────────────────────────────────────────────────────────────────

export const OrderValidationLogList = () => (
  <List
    filters={validationLogFilters}
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
      <LogTypeBadge />
      <TextField source="participant_name" label="Participant" emptyText="—" />
      <TextField source="product_name" label="Product" emptyText="—" />
      <TextField source="message" />
      <ShowButton />
    </Datagrid>
  </List>
);

// ─── Show ─────────────────────────────────────────────────────────────────────

export const OrderValidationLogShow = () => (
  <Show
    actions={
      <TopToolbar>
        <ListButton />
      </TopToolbar>
    }
  >
    <SimpleShowLayout>
      <DateField source="created_at" label="Date" showTime />
      <LogTypeBadge />
      <TextField source="participant_name" label="Participant" emptyText="—" />
      <TextField source="product_name" label="Product" emptyText="—" />
      <TextField source="message" />
      <DateField source="validated_at" label="Validated At" showTime />
    </SimpleShowLayout>
  </Show>
);
