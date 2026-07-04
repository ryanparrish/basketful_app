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
  ReferenceArrayInput,
  SelectInput,
  SelectArrayInput,
  ImageInput,
  ImageField,
  EditButton,
  ShowButton,
  FunctionField,
  useRecordContext,
  type RaRecord,
  Link,
  useSearchParams,
} from 'react-admin';
import { Chip, Box, Typography, Alert } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

// ─── List ────────────────────────────────────────────────────────────────────

export const CoachList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 2 }}>
      <Typography variant="body2">
        <strong>Coach Profiles:</strong> This page shows coaches with program assignments. 
        To manage user accounts (login credentials), go to{' '}
        <Link to="/users" style={{ fontWeight: 600 }}>Users</Link>.
      </Typography>
    </Alert>
    <Datagrid rowClick="show">
      <TextField source="name" />
      <FunctionField
        label="User Account"
        render={(record: RaRecord) =>
          record.user_username ? (
            <Chip label={record.user_username} size="small" color="primary" sx={{ fontWeight: 600 }} />
          ) : (
            <Chip label="⚠ No user linked" size="small" color="warning" variant="outlined" sx={{ fontWeight: 600 }} />
          )
        }
      />
      <EmailField source="email" />
      <TextField source="phone_number" label="Phone" />
      <FunctionField
        label="Programs"
        render={(record: RaRecord) =>
          record.program_names?.length ? (
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {record.program_names.map((p: string) => (
                <Chip key={p} label={p} size="small" />
              ))}
            </Box>
          ) : (
            <Chip label="No program" size="small" variant="outlined" />
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
        <FunctionField
          label="Programs"
          render={(record: RaRecord) =>
            record.program_names?.length ? (
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {record.program_names.map((p: string) => (
                  <Chip key={p} label={p} size="small" color="primary" variant="outlined" />
                ))}
              </Box>
            ) : (
              <Chip label="No programs assigned" size="small" variant="outlined" />
            )
          }
        />
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
      <ReferenceArrayInput source="programs" reference="programs">
        <SelectArrayInput
          optionText="name"
          label="Assigned Programs"
          helperText="Select all programs this coach manages"
          fullWidth
        />
      </ReferenceArrayInput>
      <ReferenceInput source="user" reference="users" filter={{ is_staff: true }}>
        <SelectInput
          optionText="username"
          label="User Account (Staff Only)"
          helperText="⚠️ Required for login. Select a staff user to grant them coach access. Without a linked user, this coach cannot log in to the admin."
          fullWidth
        />
      </ReferenceInput>
    </SimpleForm>
  </Edit>
);

// ─── Create ──────────────────────────────────────────────────────────────────

export const CoachCreate = () => {
  const [searchParams] = useSearchParams();
  const prefilledUser = searchParams.get('user');

  return (
    <Create>
      <SimpleForm defaultValues={prefilledUser ? { user: parseInt(prefilledUser) } : {}}>
        <Typography variant="h6" gutterBottom>Coach Profile</Typography>
        {prefilledUser && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Creating coach profile for the selected user account.
          </Alert>
        )}
        <TextInput source="name" fullWidth required />
        <TextInput source="email" type="email" fullWidth required />
        <TextInput source="phone_number" label="Phone Number" fullWidth />
        <ImageInput source="image" label="Profile Photo" accept={{ 'image/*': [] }}>
          <ImageField source="src" title="title" />
        </ImageInput>

        <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>Assignment</Typography>
        <ReferenceArrayInput source="programs" reference="programs">
          <SelectArrayInput
            optionText="name"
            label="Assigned Programs"
            helperText="Select all programs this coach manages"
            fullWidth
          />
        </ReferenceArrayInput>
        <ReferenceInput source="user" reference="users" filter={{ is_staff: true }}>
          <SelectInput
            optionText="username"
            label="User Account (Staff Only)"
            helperText="⚠️ Required for login. Select a staff user to grant them coach access. Without a linked user, this coach cannot log in to the admin."
            fullWidth
          />
        </ReferenceInput>
      </SimpleForm>
    </Create>
  );
};
