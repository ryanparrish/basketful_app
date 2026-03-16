/**
 * Order Packer Resource
 * Create and manage packers. Assign them to programs.
 * Orders are split evenly across all packers assigned to a program.
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
  ReferenceArrayInput,
  ReferenceArrayField,
  SingleFieldList,
  ChipField,
  SelectArrayInput,
  useRecordContext,
} from 'react-admin';
import { Box, Typography } from '@mui/material';

const PackerTitle = () => {
  const record = useRecordContext();
  return <span>Packer: {record?.name || ''}</span>;
};

export const OrderPackerList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="edit">
      <TextField source="name" label="Packer Name" />
      <ReferenceArrayField source="programs" reference="programs" label="Assigned Programs">
        <SingleFieldList>
          <ChipField source="name" size="small" />
        </SingleFieldList>
      </ReferenceArrayField>
      <DateField source="created_at" label="Created" />
      <EditButton />
    </Datagrid>
  </List>
);

export const OrderPackerCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" label="Packer Name" required fullWidth />
      <ReferenceArrayInput source="programs" reference="programs">
        <SelectArrayInput optionText="name" label="Assigned Programs" fullWidth />
      </ReferenceArrayInput>
      <Box sx={{ mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Orders are split evenly across all packers assigned to the same program.
          1 packer → entire order. 2 packers → orders split in half. And so on.
        </Typography>
      </Box>
    </SimpleForm>
  </Create>
);

export const OrderPackerEdit = () => (
  <Edit title={<PackerTitle />}>
    <SimpleForm>
      <TextInput source="name" label="Packer Name" required fullWidth />
      <ReferenceArrayInput source="programs" reference="programs">
        <SelectArrayInput optionText="name" label="Assigned Programs" fullWidth />
      </ReferenceArrayInput>
      <Box sx={{ mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Orders are split evenly across all packers assigned to the same program.
          1 packer → entire order. 2 packers → orders split in half. And so on.
        </Typography>
      </Box>
    </SimpleForm>
  </Edit>
);

export const OrderPackerShow = () => (
  <Show title={<PackerTitle />}>
    <SimpleShowLayout>
      <TextField source="name" label="Packer Name" />
      <ReferenceArrayField source="programs" reference="programs" label="Assigned Programs">
        <SingleFieldList>
          <ChipField source="name" />
        </SingleFieldList>
      </ReferenceArrayField>
      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />
    </SimpleShowLayout>
  </Show>
);
