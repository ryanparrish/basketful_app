/**
 * Product Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  NumberField,
  BooleanField,
  ImageField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  NumberInput,
  BooleanInput,
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
  FunctionField,
  ImageInput,
  ReferenceArrayInput,
  SelectArrayInput,
  ArrayField,
  SingleFieldList,
  ChipField,
} from 'react-admin';

const productFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <BooleanInput source="active" label="Active Only" key="active" />,
  <ReferenceInput source="category" reference="categories" key="category">
    <SelectInput optionText="name" />
  </ReferenceInput>,
  <BooleanInput source="is_meat" label="Meat Products" key="is_meat" />,
];

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <CreateButton />
    <ExportButton />
  </TopToolbar>
);

export const ProductList = () => (
  <List
    filters={productFilters}
    actions={<ListActions />}
    sort={{ field: 'name', order: 'ASC' }}
  >
    <Datagrid rowClick="show">
      <ImageField source="image" label="" sx={{ '& img': { maxWidth: 50, maxHeight: 50 } }} />
      <TextField source="name" />
      <ReferenceField source="category" reference="categories" link="show">
        <TextField source="name" />
      </ReferenceField>
      <FunctionField
        source="price"
        label="Price"
        render={(record: { price: number }) =>
          record ? `$${Number(record.price).toFixed(2)}` : ''
        }
      />
      <NumberField source="quantity_in_stock" label="Stock" />
      <BooleanField source="active" />
      <BooleanField source="is_meat" label="Meat" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

const ProductTitle = () => {
  const record = useRecordContext();
  return <span>Product: {record?.name || ''}</span>;
};

export const ProductShow = () => (
  <Show title={<ProductTitle />}>
    <SimpleShowLayout>
      <ImageField source="image" />
      <TextField source="name" />
      <TextField source="description" />
      <FunctionField
        source="price"
        label="Price"
        render={(record: { price: number }) =>
          record ? `$${Number(record.price).toFixed(2)}` : ''
        }
      />
      <ReferenceField source="category" reference="categories">
        <TextField source="name" />
      </ReferenceField>
      <ReferenceField source="subcategory" reference="subcategories">
        <TextField source="name" />
      </ReferenceField>
      <ArrayField source="tags">
        <SingleFieldList linkType={false}>
          <ChipField source="name" />
        </SingleFieldList>
      </ArrayField>
      <NumberField source="quantity_in_stock" label="Stock" />
      <NumberField source="weight_lbs" label="Weight (lbs)" />
      <NumberField source="limit" label="Purchase Limit" />
      <BooleanField source="active" />
      <BooleanField source="is_meat" label="Is Meat Product" />
    </SimpleShowLayout>
  </Show>
);

export const ProductEdit = () => (
  <Edit title={<ProductTitle />}>
    <SimpleForm>
      <TextInput source="name" required />
      <TextInput source="description" multiline rows={3} />
      <NumberInput source="price" min={0} step={0.01} required />
      <ReferenceInput source="category" reference="categories" required>
        <SelectInput optionText="name" />
      </ReferenceInput>
      <ReferenceInput source="subcategory" reference="subcategories">
        <SelectInput optionText="name" />
      </ReferenceInput>
      <ReferenceArrayInput source="tag_ids" reference="tags">
        <SelectArrayInput optionText="name" />
      </ReferenceArrayInput>
      <NumberInput source="quantity_in_stock" min={0} />
      <NumberInput source="weight_lbs" min={0} step={0.1} />
      <BooleanInput source="active" />
      <BooleanInput source="is_meat" label="Is Meat Product" />
      <ImageInput source="image" accept="image/*">
        <ImageField source="src" title="title" />
      </ImageInput>
    </SimpleForm>
  </Edit>
);

export const ProductCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" required />
      <TextInput source="description" multiline rows={3} />
      <NumberInput source="price" min={0} step={0.01} required />
      <ReferenceInput source="category" reference="categories" required>
        <SelectInput optionText="name" />
      </ReferenceInput>
      <ReferenceInput source="subcategory" reference="subcategories">
        <SelectInput optionText="name" />
      </ReferenceInput>
      <ReferenceArrayInput source="tag_ids" reference="tags">
        <SelectArrayInput optionText="name" />
      </ReferenceArrayInput>
      <NumberInput source="quantity_in_stock" min={0} defaultValue={0} />
      <NumberInput source="weight_lbs" min={0} step={0.1} />
      <BooleanInput source="active" defaultValue={true} />
      <BooleanInput source="is_meat" label="Is Meat Product" defaultValue={false} />
      <ImageInput source="image" accept="image/*">
        <ImageField source="src" title="title" />
      </ImageInput>
    </SimpleForm>
  </Create>
);
