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
  EditButton,
  ShowButton,
  FilterButton,
  CreateButton,
  ExportButton,
  TopToolbar,
  SearchInput,
  useRecordContext,
  TabbedShowLayout,
  ReferenceManyField,
  FunctionField,
} from 'react-admin';
import { Typography, Box } from '@mui/material';

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
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Details">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', mb: 2 }}>
              Basic Information
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField source="customer_number" label="Customer Number" />
              <TextField source="name" label="Name" />
              <EmailField source="email" label="Email" />
              <TextField source="phone_number" label="Phone" />
            </Box>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', mb: 2 }}>
              Program & Status
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <ReferenceField source="program" reference="programs" label="Program">
                <TextField source="name" />
              </ReferenceField>
              <BooleanField source="active" label="Active" />
              <DateField source="created_at" label="Created at" showTime />
              <DateField source="updated_at" label="Updated at" showTime />
            </Box>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', mb: 2 }}>
              Household Size
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <NumberField source="adults" label="Adults" />
              <NumberField source="children" label="Children" />
              <NumberField source="infants" label="Infants" />
            </Box>
          </Box>
          
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom sx={{ color: 'text.secondary', mb: 2 }}>
              Additional Information
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField source="dietary_restrictions" label="Dietary Restrictions" />
            </Box>
          </Box>
        </Box>
      </TabbedShowLayout.Tab>
      
      <TabbedShowLayout.Tab label="Vouchers" path="vouchers">
        <ReferenceManyField 
          reference="vouchers" 
          target="participant"
          label="Recent Vouchers"
          sort={{ field: 'created_at', order: 'DESC' }}
          perPage={10}
        >
          <Datagrid rowClick="show">
            <TextField source="voucher_number" label="Voucher #" />
            <DateField source="valid_from" label="Valid From" />
            <DateField source="valid_until" label="Valid Until" />
            <BooleanField source="redeemed" />
            <DateField source="redeemed_at" showTime />
            <FunctionField 
              label="Status" 
              render={(record: any) => {
                if (record.redeemed) return 'Redeemed';
                const now = new Date();
                const validUntil = new Date(record.valid_until);
                return validUntil < now ? 'Expired' : 'Active';
              }}
            />
            <ShowButton />
          </Datagrid>
        </ReferenceManyField>
      </TabbedShowLayout.Tab>
      
      <TabbedShowLayout.Tab label="Orders" path="orders">
        <ReferenceManyField 
          reference="orders" 
          target="participant"
          label="Recent Orders"
          sort={{ field: 'created_at', order: 'DESC' }}
          perPage={10}
        >
          <Datagrid rowClick="show">
            <TextField source="order_number" label="Order #" />
            <DateField source="created_at" label="Order Date" showTime />
            <ReferenceField source="voucher" reference="vouchers" link="show">
              <TextField source="voucher_number" />
            </ReferenceField>
            <FunctionField 
              label="Items" 
              render={(record: any) => record.items?.length || 0}
            />
            <DateField source="pickup_date" label="Pickup Date" />
            <ShowButton />
          </Datagrid>
        </ReferenceManyField>
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
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
