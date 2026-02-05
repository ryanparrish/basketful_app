/**
 * Category Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  NumberField,
  Edit,
  Create,
  SimpleForm,
  TextInput,
  Show,
  EditButton,
  ShowButton,
  ReferenceManyField,
  useRecordContext,
  TabbedShowLayout,
  ReferenceInput,
  SelectInput,
  required,
} from 'react-admin';

export const CategoryList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="show">
      <TextField source="name" />
      <NumberField source="product_count" label="Products" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

const CategoryTitle = () => {
  const record = useRecordContext();
  return <span>Category: {record?.name || ''}</span>;
};

export const CategoryShow = () => (
  <Show title={<CategoryTitle />}>
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Details">
        <TextField source="name" />
        <NumberField source="product_count" label="Active Products" />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Subcategories">
        <ReferenceManyField
          reference="subcategories"
          target="category"
          label={false}
        >
          <Datagrid rowClick="show">
            <TextField source="name" />
          </Datagrid>
        </ReferenceManyField>
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Products">
        <ReferenceManyField
          reference="products"
          target="category"
          label={false}
        >
          <Datagrid rowClick="show">
            <TextField source="name" />
            <NumberField source="price" options={{ style: 'currency', currency: 'USD' }} />
            <NumberField source="quantity_in_stock" label="Stock" />
          </Datagrid>
        </ReferenceManyField>
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

export const CategoryEdit = () => (
  <Edit title={<CategoryTitle />}>
    <SimpleForm>
      <TextInput source="name" required />
    </SimpleForm>
  </Edit>
);

export const CategoryCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" required />
    </SimpleForm>
  </Create>
);


/**
 * Subcategory Resource Components
 */
export const SubcategoryList = () => (
  <List sort={{ field: 'name', order: 'ASC' }}>
    <Datagrid rowClick="edit">
      <TextField source="name" />
      <TextField source="category_name" label="Category" />
      <EditButton />
    </Datagrid>
  </List>
);

export const SubcategoryEdit = () => (
  <Edit>
    <SimpleForm>
      <TextInput source="name" required />
      <ReferenceInput source="category" reference="categories">
        <SelectInput optionText="name" label="Category" validate={required()} />
      </ReferenceInput>
    </SimpleForm>
  </Edit>
);

export const SubcategoryCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" required />
      <ReferenceInput source="category" reference="categories">
        <SelectInput optionText="name" label="Category" validate={required()} />
      </ReferenceInput>
    </SimpleForm>
  </Create>
);
