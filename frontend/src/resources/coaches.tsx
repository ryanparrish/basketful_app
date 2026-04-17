/**
 * Coaches Resource — Lifeskills Coach CRUD for staff/admin
 */
import {
  List,
  Datagrid,
  TextField,
  EmailField,
  DateField,
  Edit,
  Create,
  Show,
  SimpleForm,
  TabbedShowLayout,
  TextInput,
  ReferenceInput,
  SelectInput,
  ImageInput,
  ImageField,
  EditButton,
  ShowButton,
  FunctionField,
  useRecordContext,
  type RaRecord,
} from 'react-admin';
import { Chip, Box, Typography } from '@mui/material';

// ─── List ────────────────────────────────────────────────────────────────────

export const CoachList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="show">
      <TextField source="name" />
      <EmailField source="email" />
      <TextField source="phone_number" label="Phone" />
      <TextField source="program_name" label="Program" />
      <FunctionField
        label="User Account"
        render={(record: RaRecord) =>
          record.user_username ? (
            <Chip label={record.user_username} size="small" color="primary" />
          ) : (
            <Chip label="No user linked" size="small" variant="outlined" />
          )
        }
      />
      <DateField source="created_at" label="Created" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

// ─── Show ────────────────────────────────────────────────────────────────────

const CoachImage = () => {
  const record = useRecordContext();
  if (!record?.image) return null;
  return (
    <Box sx={{ mb: 2 }}>
      <img
        src={record.image}
        alt={record.name}
        style={{ maxWidth: 120, maxHeight: 120, borderRadius: 8, objectFit: 'cover' }}
      />
    </Box>
  );
};

export const CoachShow = () => (
  <Show>
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Profile">
        <CoachImage />
        <TextField source="name" />
        <EmailField source="email" />
        <TextField source="phone_number" label="Phone" />
        <TextField source="program_name" label="Program" />
        <FunctionField
          label="Linked User"
          render={(record: RaRecord) =>
            record.user_username ? (
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <Chip label={record.user_username} size="small" color="primary" />
                {record.user_email && (
                  <Typography variant="body2" color="text.secondary">
                    {record.user_email}
                  </Typography>
                )}
              </Box>
            ) : (
              <Chip label="No user account linked" size="small" variant="outlined" />
            )
          }
        />
        <DateField source="created_at" label="Created" showTime />
        <DateField source="updated_at" label="Updated" showTime />
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

// ─── Edit ────────────────────────────────────────────────────────────────────

export const CoachEdit = () => (
  <Edit>
    <SimpleForm>
      <Typography variant="h6" gutterBottom>Coach Profile</Typography>
      <TextInput source="name" fullWidth required />
      <TextInput source="email" type="email" fullWidth required />
      <TextInput source="phone_number" label="Phone Number" fullWidth />
      <ImageInput source="image" label="Profile Photo" accept={{ 'image/*': [] }}>
        <ImageField source="src" title="title" />
      </ImageInput>

      <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Assignment</Typography>
      <ReferenceInput source="program" reference="programs">
        <SelectInput
          optionText="name"
          label="Assigned Program"
          helperText="The program this coach manages"
          fullWidth
        />
      </ReferenceInput>
      <ReferenceInput source="user" reference="users">
        <SelectInput
          optionText="username"
          label="Linked User Account"
          helperText="Linking a user grants them Lifeskills Coach access to this admin"
          fullWidth
        />
      </ReferenceInput>
    </SimpleForm>
  </Edit>
);

// ─── Create ──────────────────────────────────────────────────────────────────

export const CoachCreate = () => (
  <Create>
    <SimpleForm>
      <Typography variant="h6" gutterBottom>Coach Profile</Typography>
      <TextInput source="name" fullWidth required />
      <TextInput source="email" type="email" fullWidth required />
      <TextInput source="phone_number" label="Phone Number" fullWidth />
      <ImageInput source="image" label="Profile Photo" accept={{ 'image/*': [] }}>
        <ImageField source="src" title="title" />
      </ImageInput>

      <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Assignment</Typography>
      <ReferenceInput source="program" reference="programs">
        <SelectInput
          optionText="name"
          label="Assigned Program"
          helperText="The program this coach manages"
          fullWidth
        />
      </ReferenceInput>
      <ReferenceInput source="user" reference="users">
        <SelectInput
          optionText="username"
          label="Linked User Account"
          helperText="Linking a user grants them Lifeskills Coach access to this admin"
          fullWidth
        />
      </ReferenceInput>
    </SimpleForm>
  </Create>
);
