/**
 * Stock Movement Resource Components (Issue #144)
 *
 * The pantry team's stock entry: record product coming in (received,
 * donation), going out (spoilage), or a correction. Each movement updates
 * the product's stock on the server and is kept as a permanent history row.
 * Movements are never edited or deleted — a mistake is fixed by recording a
 * correction — so this resource has list, show and create only.
 */
import {
  List,
  Datagrid,
  DateField,
  TextField,
  FunctionField,
  ReferenceField,
  ReferenceInput,
  AutocompleteInput,
  SelectInput,
  NumberInput,
  TextInput,
  Create,
  SimpleForm,
  Show,
  SimpleShowLayout,
  TopToolbar,
  CreateButton,
  FilterButton,
  ExportButton,
  SearchInput,
  Button,
  required,
  useNotify,
  useRedirect,
  useRecordContext,
  type RaRecord,
} from 'react-admin';
import { Link } from 'react-router-dom';
import AddIcon from '@mui/icons-material/Add';
import {
  STOCK_MOVEMENT_KINDS,
  stockMovementErrorMessage,
  validateQuantityChange,
} from '../lib/stockMovements';

const formatChange = (value: number | null | undefined) =>
  value === null || value === undefined ? '' : value > 0 ? `+${value}` : String(value);

const stockMovementFilters = [
  <SearchInput source="q" alwaysOn key="search" />,
  <ReferenceInput source="product" reference="products" key="product">
    <AutocompleteInput optionText="name" label="Product" />
  </ReferenceInput>,
  <SelectInput source="kind" choices={STOCK_MOVEMENT_KINDS} key="kind" />,
];

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <CreateButton label="Record stock movement" />
    <ExportButton />
  </TopToolbar>
);

/** The rows of a movement history; shared by the list and the product page. */
export const StockMovementRows = ({ showProduct = true }: { showProduct?: boolean }) => (
  <Datagrid bulkActionButtons={false} rowClick="show">
    <DateField source="created_at" label="Date" showTime />
    {showProduct && (
      <ReferenceField source="product" reference="products" link="show">
        <TextField source="name" />
      </ReferenceField>
    )}
    <TextField source="kind_display" label="Kind" sortable={false} />
    <FunctionField
      source="quantity_change"
      label="Change"
      render={(record: { quantity_change: number }) => formatChange(record?.quantity_change)}
    />
    <TextField source="entered_by_name" label="Entered by" sortable={false} />
    <TextField source="note" sortable={false} />
  </Datagrid>
);

export const StockMovementList = () => (
  <List
    filters={stockMovementFilters}
    actions={<ListActions />}
    sort={{ field: 'created_at', order: 'DESC' }}
    title="Stock Movements"
  >
    <StockMovementRows />
  </List>
);

export const StockMovementShow = () => (
  <Show title="Stock Movement">
    <SimpleShowLayout>
      <DateField source="created_at" label="Date" showTime />
      <ReferenceField source="product" reference="products" link="show">
        <TextField source="name" />
      </ReferenceField>
      <TextField source="kind_display" label="Kind" />
      <FunctionField
        label="Change"
        render={(record: { quantity_change: number }) => formatChange(record?.quantity_change)}
      />
      <TextField source="entered_by_name" label="Entered by" />
      <TextField source="note" />
    </SimpleShowLayout>
  </Show>
);

export const StockMovementCreate = () => {
  const notify = useNotify();
  const redirect = useRedirect();

  return (
    <Create
      title="Record Stock Movement"
      mutationOptions={{
        onSuccess: (record: RaRecord) => {
          const data = record as RaRecord & { product: number; product_name: string; stock_after: number | null };
          const stock = data.stock_after === null ? '' : ` Stock is now ${data.stock_after}.`;
          notify(`Recorded for ${data.product_name}.${stock}`, { type: 'success' });
          // Back to the product, where the new count and history row show.
          redirect('show', 'products', data.product);
        },
        onError: (error: unknown) => {
          notify(stockMovementErrorMessage(error), { type: 'error' });
        },
      }}
    >
      <SimpleForm>
        <ReferenceInput source="product" reference="products">
          <AutocompleteInput optionText="name" label="Product" validate={required()} fullWidth />
        </ReferenceInput>
        <SelectInput
          source="kind"
          choices={STOCK_MOVEMENT_KINDS}
          validate={required()}
          defaultValue="received"
        />
        <NumberInput
          source="quantity_change"
          label="Quantity change"
          step={1}
          validate={[required(), validateQuantityChange]}
          helperText="Positive when product comes in (e.g. 24), negative when it goes out (e.g. -3)."
        />
        <TextInput
          source="note"
          multiline
          rows={2}
          fullWidth
          helperText="Optional: donor, store, or the reason for a correction."
        />
      </SimpleForm>
    </Create>
  );
};

/** "Record stock movement" button with the current product pre-filled. */
export const RecordStockMovementButton = () => {
  const record = useRecordContext();
  if (!record) return null;
  const source = encodeURIComponent(JSON.stringify({ product: record.id }));
  return (
    <Button
      component={Link}
      to={`/stock-movements/create?source=${source}`}
      label="Record stock movement"
      onClick={(event) => event.stopPropagation()}
    >
      <AddIcon />
    </Button>
  );
};
