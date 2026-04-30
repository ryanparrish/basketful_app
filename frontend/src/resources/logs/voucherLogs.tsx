/**
 * VoucherLog Resource — read-only audit trail of voucher events.
 * Mirrors VoucherLog in apps/log/models.py
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
import { LogTypeBadge } from './shared';

const LOG_TYPE_CHOICES = [
  { id: 'INFO', name: 'Info' },
  { id: 'WARNING', name: 'Warning' },
  { id: 'ERROR', name: 'Error' },
];

const voucherLogFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <SelectInput source="log_type" choices={LOG_TYPE_CHOICES} key="log_type" />,
];

// ─── List ─────────────────────────────────────────────────────────────────────

export const VoucherLogList = () => (
  <List
    filters={voucherLogFilters}
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
      <TextField source="message" />
      <NumberField
        source="balance_before"
        label="Balance Before"
        options={{ style: 'currency', currency: 'USD' }}
      />
      <NumberField
        source="balance_after"
        label="Balance After"
        options={{ style: 'currency', currency: 'USD' }}
      />
      <ShowButton />
    </Datagrid>
  </List>
);

// ─── Show ─────────────────────────────────────────────────────────────────────

export const VoucherLogShow = () => (
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
      <TextField source="message" />
      <NumberField
        source="balance_before"
        label="Balance Before"
        options={{ style: 'currency', currency: 'USD' }}
      />
      <NumberField
        source="balance_after"
        label="Balance After"
        options={{ style: 'currency', currency: 'USD' }}
      />
      <NumberField
        source="applied_amount"
        label="Applied Amount"
        options={{ style: 'currency', currency: 'USD' }}
      />
      <NumberField
        source="remaining"
        label="Remaining"
        options={{ style: 'currency', currency: 'USD' }}
      />
      <DateField source="validated_at" label="Validated At" showTime />
    </SimpleShowLayout>
  </Show>
);
