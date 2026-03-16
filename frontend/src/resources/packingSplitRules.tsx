/**
 * PackingSplitRule Resource — category-to-packer mapping configuration.
 * Mirrors PackingSplitRuleAdmin from apps/orders/admin.py
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  ReferenceField,
  Show,
  SimpleShowLayout,
  Create,
  Edit,
  SimpleForm,
  ReferenceInput,
  SelectInput,
  ReferenceArrayInput,
  SelectArrayInput,
  TopToolbar,
  ListButton,
  EditButton,
  FilterButton,
  CreateButton,
  ExportButton,
  SearchInput,
  FunctionField,
  useRecordContext,
  required,
  type RaRecord,
} from 'react-admin';
import { Box, Chip, Typography } from '@mui/material';

// ─── Field Components ───────────────────────────────────────────────────────

const CategoryChipsField = () => {
  const record = useRecordContext();
  if (!record) return null;
  const names: string[] = record.category_names || [];
  const displayNames = names.slice(0, 5);
  const hasMore = names.length > 5;
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
      {displayNames.map((name) => (
        <Chip key={name} label={name} size="small" color="primary" variant="outlined" />
      ))}
      {hasMore && (
        <Chip label={`+${names.length - 5} more`} size="small" variant="outlined" />
      )}
      {names.length === 0 && (
        <Typography variant="body2" color="text.secondary">None</Typography>
      )}
    </Box>
  );
};

const SubcategoryChipsField = () => {
  const record = useRecordContext();
  if (!record) return null;
  const names: string[] = record.subcategory_names || [];
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
      {names.map((name) => (
        <Chip key={name} label={name} size="small" variant="outlined" />
      ))}
      {names.length === 0 && (
        <Typography variant="body2" color="text.secondary">None</Typography>
      )}
    </Box>
  );
};

// ─── Filters ────────────────────────────────────────────────────────────────

const packingSplitRuleFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <ReferenceInput source="program" reference="programs" key="program">
    <SelectInput optionText="name" label="Program" />
  </ReferenceInput>,
  <ReferenceInput source="packer" reference="order-packers" key="packer">
    <SelectInput optionText="name" label="Packer" />
  </ReferenceInput>,
];

// ─── List ────────────────────────────────────────────────────────────────────

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <CreateButton />
    <ExportButton />
  </TopToolbar>
);

export const PackingSplitRuleList = () => (
  <List
    filters={packingSplitRuleFilters}
    actions={<ListActions />}
    sort={{ field: 'created_at', order: 'DESC' }}
  >
    <Datagrid rowClick="show" bulkActionButtons={false}>
      <ReferenceField source="program" reference="programs" link="show">
        <TextField source="name" />
      </ReferenceField>
      <ReferenceField source="packer" reference="order-packers" link={false}>
        <TextField source="name" />
      </ReferenceField>
      <FunctionField
        label="Categories"
        render={() => <CategoryChipsField />}
      />
      <DateField source="created_at" />
      <EditButton />
    </Datagrid>
  </List>
);

// ─── Show ────────────────────────────────────────────────────────────────────

const ShowActions = () => (
  <TopToolbar>
    <ListButton />
    <EditButton />
  </TopToolbar>
);

export const PackingSplitRuleShow = () => (
  <Show actions={<ShowActions />}>
    <SimpleShowLayout>
      <ReferenceField source="program" reference="programs" link="show">
        <TextField source="name" label="Program" />
      </ReferenceField>
      <ReferenceField source="packer" reference="order-packers" link={false}>
        <TextField source="name" label="Packer" />
      </ReferenceField>

      <Typography variant="h6" sx={{ mt: 2, mb: 0.5 }}>Category Assignments</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Categories and subcategories this packer is responsible for.
      </Typography>

      <FunctionField label="Categories" render={() => <CategoryChipsField />} />
      <FunctionField label="Subcategories" render={() => <SubcategoryChipsField />} />

      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />
    </SimpleShowLayout>
  </Show>
);

// ─── Create ──────────────────────────────────────────────────────────────────

export const PackingSplitRuleCreate = () => (
  <Create>
    <SimpleForm>
      <ReferenceInput source="program" reference="programs">
        <SelectInput
          optionText="name"
          fullWidth
          validate={required()}
          helperText="Select the program this rule applies to"
        />
      </ReferenceInput>
      <ReferenceInput source="packer" reference="order-packers">
        <SelectInput
          optionText="name"
          fullWidth
          validate={required()}
          helperText="Select the packer assigned to these categories"
        />
      </ReferenceInput>

      <Typography variant="subtitle1" sx={{ mt: 2, fontWeight: 'bold' }}>
        Category Assignments
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Select which categories/subcategories this packer is responsible for.
      </Typography>

      <ReferenceArrayInput source="categories" reference="categories">
        <SelectArrayInput
          optionText="name"
          fullWidth
          helperText="Assign top-level categories to this packer"
        />
      </ReferenceArrayInput>
      <ReferenceArrayInput source="subcategories" reference="subcategories">
        <SelectArrayInput
          optionText={(record: RaRecord) => `${record.name} (${record.category_name})`}
          fullWidth
          helperText="Assign specific subcategories to this packer"
        />
      </ReferenceArrayInput>
    </SimpleForm>
  </Create>
);

// ─── Edit ────────────────────────────────────────────────────────────────────

export const PackingSplitRuleEdit = () => (
  <Edit>
    <SimpleForm>
      <ReferenceInput source="program" reference="programs">
        <SelectInput optionText="name" fullWidth disabled helperText="Program cannot be changed" />
      </ReferenceInput>
      <ReferenceInput source="packer" reference="order-packers">
        <SelectInput
          optionText="name"
          fullWidth
          validate={required()}
        />
      </ReferenceInput>

      <Typography variant="subtitle1" sx={{ mt: 2, fontWeight: 'bold' }}>
        Category Assignments
      </Typography>

      <ReferenceArrayInput source="categories" reference="categories">
        <SelectArrayInput optionText="name" fullWidth />
      </ReferenceArrayInput>
      <ReferenceArrayInput source="subcategories" reference="subcategories">
        <SelectArrayInput
          optionText={(record: RaRecord) => `${record.name} (${record.category_name})`}
          fullWidth
        />
      </ReferenceArrayInput>
    </SimpleForm>
  </Edit>
);
