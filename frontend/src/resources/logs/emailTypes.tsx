/**
 * EmailType Resource — Full CRUD.
 * Mirrors EmailTypeAdmin from apps/log/admin.py
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  BooleanField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  BooleanInput,
  Show,
  TabbedShowLayout,
  TopToolbar,
  EditButton,
  ShowButton,
  ListButton,
  FilterButton,
  SearchInput,
  useRecordContext,
} from 'react-admin';
import { Typography } from '@mui/material';
import { ActiveChip } from './shared';
import { TinyMCEInput } from '../../components/TinyMCEInput';
import { EmailServerPreview } from './EmailServerPreview';

// ─── List ─────────────────────────────────────────────────────────────────────

const emailTypeFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
];

export const EmailTypeList = () => (
  <List
    filters={emailTypeFilters}
    sort={{ field: 'display_name', order: 'ASC' }}
    perPage={25}
    actions={
      <TopToolbar>
        <FilterButton />
      </TopToolbar>
    }
  >
    <Datagrid rowClick="show" bulkActionButtons={false}>
      <TextField source="display_name" label="Name" />
      <TextField source="name" label="Slug" />
      <TextField source="subject" />
      <ActiveChip />
      <DateField source="updated_at" label="Last Updated" showTime />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

// ─── Show ─────────────────────────────────────────────────────────────────────

const ServerPreviewField = () => {
  const record = useRecordContext();
  if (!record) return null;
  if (!record.html_content && !record.html_template) {
    return <Typography variant="body2" color="text.secondary">—</Typography>;
  }
  return <EmailServerPreview emailTypeId={record.id} />;
};
ServerPreviewField.displayName = 'ServerPreviewField';

export const EmailTypeShow = () => (
  <Show
    actions={
      <TopToolbar>
        <ListButton />
        <EditButton />
      </TopToolbar>
    }
  >
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Summary">
        <TextField source="display_name" label="Name" />
        <TextField source="name" label="Slug" />
        <TextField source="subject" />
        <BooleanField source="is_active" />
        <DateField source="created_at" showTime />
        <DateField source="updated_at" showTime />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Preview">
        <ServerPreviewField />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Settings">
        <TextField source="from_email" label="From Email" emptyText="(uses default)" />
        <TextField source="reply_to" label="Reply-To" emptyText="(uses default)" />
        <TextField source="html_template" label="HTML Template File" emptyText="—" />
        <TextField source="text_template" label="Text Template File" emptyText="—" />
        <TextField source="available_variables" label="Available Variables" />
        <TextField source="description" />
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

// ─── Edit ─────────────────────────────────────────────────────────────────────

export const EmailTypeEdit = () => (
  <Edit
    actions={
      <TopToolbar>
        <ListButton />
        <ShowButton />
      </TopToolbar>
    }
  >
    <SimpleForm>
      <TextInput source="display_name" label="Name" fullWidth required />
      <TextInput source="name" label="Slug (internal ID)" fullWidth required />
      <BooleanInput source="is_active" />

      <Typography variant="h6" sx={{ mt: 2 }}>English Content</Typography>
      <TextInput source="subject_en" label="Subject (English)" fullWidth helperText="Supports {{ variable }} template syntax" />
      <TinyMCEInput
        source="html_content_en"
        label="HTML Content (English)"
        height={500}
        helperText="Full HTML document. Overrides template file. Supports Django template syntax."
      />
      <TextInput
        source="text_content_en"
        label="Plain Text Content (English)"
        multiline
        minRows={5}
        fullWidth
      />

      <Typography variant="h6" sx={{ mt: 2 }}>Spanish Content</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Leave blank to fall back to the English version.
      </Typography>
      <TextInput source="subject_es" label="Subject (Spanish)" fullWidth />
      <TinyMCEInput
        source="html_content_es"
        label="HTML Content (Spanish)"
        height={400}
      />
      <TextInput
        source="text_content_es"
        label="Plain Text Content (Spanish)"
        multiline
        minRows={5}
        fullWidth
      />

      <Typography variant="h6" sx={{ mt: 2 }}>Settings</Typography>
      <TextInput source="from_email" label="From Email" fullWidth helperText="Leave blank for global default" />
      <TextInput source="reply_to" label="Reply-To" fullWidth helperText="Leave blank for global default" />
      <TextInput source="html_template" label="HTML Template File Path" fullWidth />
      <TextInput source="text_template" label="Text Template File Path" fullWidth />
      <TextInput source="description" multiline minRows={3} fullWidth />
      <TextInput source="available_variables" label="Available Variables (docs)" multiline minRows={3} fullWidth />
    </SimpleForm>
  </Edit>
);

// ─── Create ───────────────────────────────────────────────────────────────────

export const EmailTypeCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="display_name" label="Name" fullWidth required />
      <TextInput source="name" label="Slug (internal ID)" fullWidth required />
      <TextInput source="subject" fullWidth required helperText="Supports {{ variable }} template syntax" />
      <BooleanInput source="is_active" defaultValue={true} />
      <TinyMCEInput
        source="html_content"
        label="HTML Content"
        height={500}
        helperText="Full HTML document. Supports Django template syntax."
      />
      <TextInput
        source="text_content"
        label="Plain Text Content"
        multiline
        minRows={5}
        fullWidth
      />
      <TextInput source="from_email" label="From Email" fullWidth />
      <TextInput source="reply_to" label="Reply-To" fullWidth />
    </SimpleForm>
  </Create>
);
