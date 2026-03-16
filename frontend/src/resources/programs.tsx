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
  FunctionField,
  Button,
} from 'react-admin';
import { Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';

const MEETING_DAY_CHOICES = [
  { id: 'monday', name: 'Monday' },
  { id: 'tuesday', name: 'Tuesday' },
  { id: 'wednesday', name: 'Wednesday' },
  { id: 'thursday', name: 'Thursday' },
  { id: 'friday', name: 'Friday' },
];

const SPLIT_STRATEGY_CHOICES = [
  { id: 'fifty_fifty', name: '50/50 Split' },
  { id: 'round_robin', name: 'Round Robin' },
];

const STRATEGY_LABELS: Record<string, string> = {
  none: 'None (Single Packer)',
  fifty_fifty: '50/50 Split',
  round_robin: 'Round Robin',
  by_category: 'By Category',
};

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

export const ProgramShow = () => {
  const navigate = useNavigate();
  return (
    <Show title={<ProgramTitle />}>
      <TabbedShowLayout>
        <TabbedShowLayout.Tab label="Details">
          <TextField source="name" />
          <TextField source="MeetingDay" label="Meeting Day" />
          <TextField source="meeting_time" label="Meeting Time" />
          <TextField source="meeting_address" label="Address" />
          <FunctionField
            source="default_split_strategy"
            label="Default Split Strategy"
            render={(record: { default_split_strategy: string }) =>
              STRATEGY_LABELS[record.default_split_strategy] || record.default_split_strategy
            }
          />
          <NumberField source="participant_count" label="Total Participants" />
          <NumberField source="active_participant_count" label="Active Participants" />
          <DateField source="created_at" showTime />
          <DateField source="updated_at" showTime />
        </TabbedShowLayout.Tab>
        <TabbedShowLayout.Tab label="Participants">
          <ReferenceManyField reference="participants" target="program" label={false}>
            <Datagrid rowClick="show">
              <TextField source="customer_number" label="Customer #" />
              <TextField source="name" />
              <TextField source="email" />
              <NumberField source="adults" />
              <NumberField source="children" />
            </Datagrid>
          </ReferenceManyField>
        </TabbedShowLayout.Tab>
        <TabbedShowLayout.Tab label="Packers">
          <PackersTab navigate={navigate} />
        </TabbedShowLayout.Tab>
      </TabbedShowLayout>
    </Show>
  );
};

const PackersTab = ({ navigate }: { navigate: ReturnType<typeof useNavigate> }) => {
  return (
    <Box sx={{ p: 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Box component="h3" sx={{ m: 0, fontSize: '1rem', fontWeight: 600 }}>Assigned Packers</Box>
        <Button
          label="Create Packer"
          onClick={() => navigate('/order-packers/create')}
          size="small"
          variant="contained"
        />
      </Box>
      <Box sx={{ color: 'text.secondary', fontSize: '0.85rem', mb: 2 }}>
        Orders are split evenly across all assigned packers. One packer gets all orders; two packers split in half; three get thirds; etc.
      </Box>
      <ReferenceManyField reference="order-packers" target="programs" label={false}>
        <Datagrid
          bulkActionButtons={false}
          empty={
            <Box sx={{ color: 'text.secondary', py: 2, pl: 1 }}>
              No packers assigned to this program yet.
            </Box>
          }
        >
          <TextField source="name" label="Packer" />
          <FunctionField
            label="All Programs"
            render={(rec: { program_names: string[] }) =>
              (rec.program_names || []).join(', ') || '—'
            }
          />
          <FunctionField
            label=""
            render={(rec: { id: number }) => (
              <Button
                label="Edit Packer"
                onClick={() => navigate(`/order-packers/${rec.id}`)}
                size="small"
              />
            )}
          />
        </Datagrid>
      </ReferenceManyField>
    </Box>
  );
};

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
