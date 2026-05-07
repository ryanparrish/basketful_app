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
import { Box, Typography } from '@mui/material';
import { ActiveChip } from './shared';
import { TinyMCEInput } from '../../components/TinyMCEInput';

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

const HtmlPreviewField = () => {
  const record = useRecordContext();
  if (!record) return null;
  const content = record.html_content || record.html_template;
  if (!content) return <Typography variant="body2" color="text.secondary">—</Typography>;
  if (record.html_content) {
    return (
      <Box sx={{ border: '1px solid #e0e0e0', borderRadius: 1, overflow: 'hidden' }}>
        <iframe
          srcDoc={record.html_content}
          style={{ width: '100%', height: 500, border: 'none', display: 'block' }}
          sandbox="allow-same-origin"
          title="Email HTML Preview"
        />
      </Box>
    );
  }
  return (
    <Typography variant="body2" color="text.secondary">
      📄 Template file: <code>{content}</code>
    </Typography>
  );
};
HtmlPreviewField.displayName = 'HtmlPreviewField';

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
      <TabbedShowLayout.Tab label="HTML Content">
        <HtmlPreviewField />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Text Content">
        <TextField source="text_content" component="pre" />
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
      <TextInput source="subject" fullWidth required helperText="Supports {{ variable }} template syntax" />
      <BooleanInput source="is_active" />
      <TinyMCEInput
        source="html_content"
        label="HTML Content"
        height={500}
        helperText="Full HTML document. Overrides template file. Supports Django template syntax."
      />
      <TextInput
        source="text_content"
        label="Plain Text Content"
        multiline
        minRows={5}
        fullWidth
      />
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
