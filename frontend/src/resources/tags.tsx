/**
 * Tag Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  Show,
  SimpleShowLayout,
  EditButton,
  ShowButton,
  required,
} from 'react-admin';

export const TagList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="edit">
      <TextField source="name" />
      <TextField source="slug" />
      <TextField source="description" />
      <DateField source="created_at" label="Created" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

export const TagShow = () => (
  <Show>
    <SimpleShowLayout>
      <TextField source="name" />
      <TextField source="slug" />
      <TextField source="description" />
      <DateField source="created_at" label="Created" showTime />
      <DateField source="updated_at" label="Last Updated" showTime />
    </SimpleShowLayout>
  </Show>
);

export const TagEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="name" validate={required()} />
      <TextInput source="slug" validate={required()} helperText="URL-friendly version of name (auto-generated from name)" />
      <TextInput source="description" multiline rows={3} />
    </SimpleForm>
  </Edit>
);

export const TagCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" validate={required()} />
      <TextInput source="slug" validate={required()} helperText="URL-friendly version of name (auto-generated from name)" />
      <TextInput source="description" multiline rows={3} />
    </SimpleForm>
  </Create>
);
