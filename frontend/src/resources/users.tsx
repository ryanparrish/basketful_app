/**
 * Users Resource - Manage users and their groups
 */
import {
  List,
  Datagrid,
  TextField,
  EmailField,
  BooleanField,
  Show,
  TabbedShowLayout,
  Tab,
  Edit,
  SimpleForm,
  Create,
  TextInput,
  BooleanInput,
  ReferenceArrayInput,
  SelectArrayInput,
  FunctionField,
  required,
  email,
  useRecordContext,
} from 'react-admin';
import { Chip, Box } from '@mui/material';

// List
export const UserList = () => (
  <List>
    <Datagrid rowClick="show">
      <TextField source="id" />
      <TextField source="username" />
      <EmailField source="email" />
      <TextField source="first_name" />
      <TextField source="last_name" />
      <BooleanField source="is_staff" />
      <BooleanField source="is_superuser" />
      <BooleanField source="is_active" />
      <FunctionField
        label="Groups"
        render={(record: any) => (
          <span>{record.groups?.length || 0} groups</span>
        )}
      />
    </Datagrid>
  </List>
);

// Show
export const UserShow = () => {
  const UserGroups = () => {
    const record = useRecordContext();
    if (!record || !record.group_details) return null;

    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
        {record.group_details.map((group: any) => (
          <Chip
            key={group.id}
            label={group.name}
            size="small"
            color="primary"
            variant="outlined"
          />
        ))}
      </Box>
    );
  };

  const UserPermissions = () => {
    const record = useRecordContext();
    if (!record || !record.all_permissions) return null;

    if (record.all_permissions.includes('*')) {
      return <Chip label="All Permissions (Superuser)" color="error" />;
    }

    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
        {record.all_permissions.slice(0, 20).map((perm: string) => (
          <Chip
            key={perm}
            label={perm}
            size="small"
            variant="outlined"
          />
        ))}
        {record.all_permissions.length > 20 && (
          <Chip
            label={`+${record.all_permissions.length - 20} more`}
            size="small"
            variant="outlined"
          />
        )}
      </Box>
    );
  };

  return (
    <Show>
      <TabbedShowLayout>
        <Tab label="Basic Info">
          <TextField source="id" />
          <TextField source="username" />
          <EmailField source="email" />
          <TextField source="first_name" />
          <TextField source="last_name" />
          <BooleanField source="is_staff" />
          <BooleanField source="is_superuser" />
          <BooleanField source="is_active" />
        </Tab>
        <Tab label="Groups">
          <FunctionField label="Groups" render={() => <UserGroups />} />
        </Tab>
        <Tab label="Permissions">
          <FunctionField label="Effective Permissions" render={() => <UserPermissions />} />
        </Tab>
      </TabbedShowLayout>
    </Show>
  );
};

// Edit
export const UserEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="username" validate={required()} fullWidth disabled />
      <TextInput source="email" validate={[required(), email()]} fullWidth />
      <TextInput source="first_name" fullWidth />
      <TextInput source="last_name" fullWidth />
      <BooleanInput source="is_staff" />
      <BooleanInput source="is_active" />
      <ReferenceArrayInput source="groups" reference="groups">
        <SelectArrayInput optionText="name" fullWidth />
      </ReferenceArrayInput>
    </SimpleForm>
  </Edit>
);

// Create
export const UserCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="username" validate={required()} fullWidth />
      <TextInput source="email" validate={[required(), email()]} fullWidth />
      <TextInput source="password" type="password" validate={required()} fullWidth />
      <TextInput source="first_name" fullWidth />
      <TextInput source="last_name" fullWidth />
      <BooleanInput source="is_staff" />
      <BooleanInput source="is_active" defaultValue={true} />
      <ReferenceArrayInput source="groups" reference="groups">
        <SelectArrayInput optionText="name" fullWidth />
      </ReferenceArrayInput>
    </SimpleForm>
  </Create>
);
