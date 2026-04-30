/**
 * UserLoginLog Resource — read-only login/logout audit trail.
 * Mirrors UserLoginLogAdmin from apps/log/admin.py
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
import { LoginActionBadge } from './shared';

const ACTION_CHOICES = [
  { id: 'login', name: 'Login' },
  { id: 'logout', name: 'Logout' },
  { id: 'failed_login', name: 'Failed Login' },
];

const loginLogFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <SelectInput source="action" choices={ACTION_CHOICES} key="action" />,
];

// ─── List ─────────────────────────────────────────────────────────────────────

export const UserLoginLogList = () => (
  <List
    filters={loginLogFilters}
    sort={{ field: 'timestamp', order: 'DESC' }}
    perPage={25}
    actions={
      <TopToolbar>
        <FilterButton />
        <ExportButton />
      </TopToolbar>
    }
  >
    <Datagrid rowClick="show" bulkActionButtons={false}>
      <DateField source="timestamp" label="Time" showTime />
      <TextField source="username" label="User" emptyText="—" />
      <TextField source="username_attempted" label="Attempted Username" emptyText="—" />
      <LoginActionBadge />
      <TextField source="participant_name" label="Participant" emptyText="—" />
      <TextField source="ip_address" label="IP Address" emptyText="—" />
      <ShowButton />
    </Datagrid>
  </List>
);

// ─── Show ─────────────────────────────────────────────────────────────────────

export const UserLoginLogShow = () => (
  <Show
    actions={
      <TopToolbar>
        <ListButton />
      </TopToolbar>
    }
  >
    <SimpleShowLayout>
      <DateField source="timestamp" label="Time" showTime />
      <TextField source="username" label="User" emptyText="—" />
      <TextField source="username_attempted" label="Attempted Username" emptyText="—" />
      <LoginActionBadge />
      <TextField source="participant_name" label="Participant" emptyText="—" />
      <TextField source="ip_address" label="IP Address" emptyText="—" />
      <TextField source="user_agent" label="User Agent" emptyText="—" />
    </SimpleShowLayout>
  </Show>
);
