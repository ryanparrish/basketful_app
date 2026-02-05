/**
 * Permissions Resource - View available permissions (read-only)
 */
import {
  List,
  Datagrid,
  TextField,
  Show,
  SimpleShowLayout,
  FilterList,
  FilterListItem,
} from 'react-admin';
import { Card, CardContent } from '@mui/material';

// Filters
const PermissionFilters = () => {
  return (
    <Card sx={{ order: -1, mr: 2, mt: 8, width: 200 }}>
      <CardContent>
        <FilterList label="App" icon={null}>
          <FilterListItem
            label="Orders"
            value={{ app_label: 'orders' }}
          />
          <FilterListItem
            label="Voucher"
            value={{ app_label: 'voucher' }}
          />
          <FilterListItem
            label="Account"
            value={{ app_label: 'account' }}
          />
          <FilterListItem
            label="Lifeskills"
            value={{ app_label: 'lifeskills' }}
          />
          <FilterListItem
            label="Pantry"
            value={{ app_label: 'pantry' }}
          />
          <FilterListItem
            label="Auth"
            value={{ app_label: 'auth' }}
          />
        </FilterList>
      </CardContent>
    </Card>
  );
};

// List
export const PermissionList = () => (
  <List aside={<PermissionFilters />} perPage={50}>
    <Datagrid rowClick="show">
      <TextField source="id" />
      <TextField source="app_label" label="App" />
      <TextField source="model" label="Model" />
      <TextField source="codename" label="Codename" />
      <TextField source="name" label="Name" />
    </Datagrid>
  </List>
);

// Show
export const PermissionShow = () => (
  <Show>
    <SimpleShowLayout>
      <TextField source="id" />
      <TextField source="name" label="Name" />
      <TextField source="codename" label="Codename" />
      <TextField source="app_label" label="App Label" />
      <TextField source="model" label="Model" />
    </SimpleShowLayout>
  </Show>
);
