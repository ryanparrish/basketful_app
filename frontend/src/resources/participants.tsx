/**
 * Participant Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  EmailField,
  BooleanField,
  DateField,
  NumberField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  BooleanInput,
  NumberInput,
  ReferenceInput,
  SelectInput,
  ReferenceField,
  Show,
  SimpleShowLayout,
  EditButton,
  ShowButton,
  FilterButton,
  CreateButton,
  ExportButton,
  TopToolbar,
  SearchInput,
  useRecordContext,
} from 'react-admin';

const participantFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <BooleanInput source="active" label="Active Only" key="active" />,
  <ReferenceInput source="program" reference="programs" key="program">
    <SelectInput optionText="name" />
  </ReferenceInput>,
];

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <CreateButton />
    <ExportButton />
  </TopToolbar>
);

export const ParticipantList = () => (
  <List filters={participantFilters} actions={<ListActions />} sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="show">
      <TextField source="customer_number" label="Customer #" />
      <TextField source="name" />
      <EmailField source="email" />
      <ReferenceField source="program" reference="programs" link="show">
        <TextField source="name" />
      </ReferenceField>
      <BooleanField source="active" />
      <NumberField source="adults" />
      <NumberField source="children" />
      <DateField source="created_at" label="Joined" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

const ParticipantTitle = () => {
  const record = useRecordContext();
  return <span>Participant: {record?.name || ''}</span>;
};

export const ParticipantShow = () => (
  <Show title={<ParticipantTitle />}>
    <SimpleShowLayout>
      <TextField source="customer_number" label="Customer Number" />
      <TextField source="name" />
      <EmailField source="email" />
      <TextField source="phone_number" label="Phone" />
      <ReferenceField source="program" reference="programs">
        <TextField source="name" />
      </ReferenceField>
      <BooleanField source="active" />
      <NumberField source="adults" />
      <NumberField source="children" />
      <NumberField source="infants" />
      <TextField source="dietary_restrictions" />
      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />
    </SimpleShowLayout>
  </Show>
);

export const ParticipantEdit = () => (
  <Edit title={<ParticipantTitle />}>
    <SimpleForm>
      <TextInput source="name" required />
      <TextInput source="email" type="email" />
      <TextInput source="phone_number" label="Phone Number" />
      <ReferenceInput source="program" reference="programs">
        <SelectInput optionText="name" />
      </ReferenceInput>
      <BooleanInput source="active" />
      <NumberInput source="adults" min={0} />
      <NumberInput source="children" min={0} />
      <NumberInput source="infants" min={0} />
      <TextInput source="dietary_restrictions" multiline rows={3} />
    </SimpleForm>
  </Edit>
);

export const ParticipantCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" required />
      <TextInput source="email" type="email" />
      <TextInput source="phone_number" label="Phone Number" />
      <ReferenceInput source="program" reference="programs" required>
        <SelectInput optionText="name" />
      </ReferenceInput>
      <BooleanInput source="active" defaultValue={true} />
      <NumberInput source="adults" min={0} defaultValue={1} />
      <NumberInput source="children" min={0} defaultValue={0} />
      <NumberInput source="infants" min={0} defaultValue={0} />
      <TextInput source="dietary_restrictions" multiline rows={3} />
    </SimpleForm>
  </Create>
);
