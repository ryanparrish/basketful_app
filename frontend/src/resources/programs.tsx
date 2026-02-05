/**
 * Program Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  NumberField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  SelectInput,
  Show,
  EditButton,
  ShowButton,
  ReferenceManyField,
  useRecordContext,
  TabbedShowLayout,
} from 'react-admin';

const MEETING_DAY_CHOICES = [
  { id: 'monday', name: 'Monday' },
  { id: 'tuesday', name: 'Tuesday' },
  { id: 'wednesday', name: 'Wednesday' },
  { id: 'thursday', name: 'Thursday' },
  { id: 'friday', name: 'Friday' },
];

const SPLIT_STRATEGY_CHOICES = [
  { id: 'none', name: 'None (Single Packer)' },
  { id: 'fifty_fifty', name: '50/50 Split' },
  { id: 'round_robin', name: 'Round Robin' },
  { id: 'by_category', name: 'By Category' },
];

export const ProgramList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="show">
      <TextField source="name" />
      <TextField source="MeetingDay" label="Meeting Day" />
      <TextField source="meeting_time" label="Time" />
      <NumberField source="participant_count" label="Participants" />
      <TextField source="default_split_strategy" label="Split Strategy" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

const ProgramTitle = () => {
  const record = useRecordContext();
  return <span>Program: {record?.name || ''}</span>;
};

export const ProgramShow = () => (
  <Show title={<ProgramTitle />}>
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Details">
        <TextField source="name" />
        <TextField source="MeetingDay" label="Meeting Day" />
        <TextField source="meeting_time" label="Meeting Time" />
        <TextField source="meeting_address" label="Address" />
        <TextField source="default_split_strategy" label="Default Split Strategy" />
        <NumberField source="participant_count" label="Total Participants" />
        <NumberField source="active_participant_count" label="Active Participants" />
        <DateField source="created_at" showTime />
        <DateField source="updated_at" showTime />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Participants">
        <ReferenceManyField
          reference="participants"
          target="program"
          label={false}
        >
          <Datagrid rowClick="show">
            <TextField source="customer_number" label="Customer #" />
            <TextField source="name" />
            <TextField source="email" />
            <NumberField source="adults" />
            <NumberField source="children" />
          </Datagrid>
        </ReferenceManyField>
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

export const ProgramEdit = () => (
  <Edit title={<ProgramTitle />}>
    <SimpleForm>
      <TextInput source="name" required />
      <SelectInput source="MeetingDay" choices={MEETING_DAY_CHOICES} required />
      <TextInput source="meeting_time" type="time" required />
      <TextInput source="meeting_address" multiline rows={2} required />
      <SelectInput
        source="default_split_strategy"
        choices={SPLIT_STRATEGY_CHOICES}
      />
    </SimpleForm>
  </Edit>
);

export const ProgramCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" required />
      <SelectInput source="MeetingDay" choices={MEETING_DAY_CHOICES} required />
      <TextInput source="meeting_time" type="time" defaultValue="09:00" required />
      <TextInput source="meeting_address" multiline rows={2} required />
      <SelectInput
        source="default_split_strategy"
        choices={SPLIT_STRATEGY_CHOICES}
        defaultValue="none"
      />
    </SimpleForm>
  </Create>
);
