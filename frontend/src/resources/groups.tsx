/**
 * Groups Resource - Manage user groups and permissions
 */
import {
  List,
  Datagrid,
  TextField,
  Show,
  SimpleShowLayout,
  Edit,
  SimpleForm,
  Create,
  TextInput,
  ReferenceArrayInput,
  SelectArrayInput,
  FunctionField,
  required,
  useRecordContext,
  type RaRecord,
} from 'react-admin';
import { Chip, Box } from '@mui/material';

// List
export const GroupList = () => (
  <List>
    <Datagrid rowClick="show">
      <TextField source="id" />
      <TextField source="name" />
      <FunctionField
        label="Permissions"
        render={(record: RaRecord) => (
          <span>{record.permissions?.length || 0} permissions</span>
        )}
      />
      <FunctionField
        label="Users"
        render={(record: RaRecord) => (
          <span>{record.user_count || 0} users</span>
        )}
      />
    </Datagrid>
  </List>
);

// Show
export const GroupShow = () => {
  const GroupPermissions = () => {
    const record = useRecordContext();
    if (!record || !record.permission_details) return null;

    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
        {record.permission_details.map((perm: RaRecord) => (
          <Chip
            key={perm.id}
            label={`${perm.app_label}.${perm.codename}`}
            size="small"
            variant="outlined"
          />
        ))}
      </Box>
    );
  };

  return (
    <Show>
      <SimpleShowLayout>
        <TextField source="id" />
        <TextField source="name" />
        <FunctionField
          label="Users"
          render={(record: RaRecord) => `${record.user_count || 0} users`}
        />
        <FunctionField
          label="Permissions"
          render={() => <GroupPermissions />}
        />
      </SimpleShowLayout>
    </Show>
  );
};

// Edit
export const GroupEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="name" validate={required()} fullWidth />
      <ReferenceArrayInput source="permissions" reference="permissions">
        <SelectArrayInput
          optionText={(choice: RaRecord) =>
            `${choice.app_label}.${choice.codename} - ${choice.name}`
          }
          fullWidth
        />
      </ReferenceArrayInput>
    </SimpleForm>
  </Edit>
);

// Create
export const GroupCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" validate={required()} fullWidth />
      <ReferenceArrayInput source="permissions" reference="permissions">
        <SelectArrayInput
          optionText={(choice: RaRecord) =>
            `${choice.app_label}.${choice.codename} - ${choice.name}`
          }
          fullWidth
        />
      </ReferenceArrayInput>
    </SimpleForm>
  </Create>
);
