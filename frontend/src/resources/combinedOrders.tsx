/**
 * Combined Order Resource Components
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
  ReferenceInput,
  ReferenceField,
  Show,
  TabbedShowLayout,
  EditButton,
  ShowButton,
  FilterButton,
  CreateButton,
  ExportButton,
  TopToolbar,
  useRecordContext,
  ArrayField,
  FunctionField,
  Button,
  useDataProvider,
  useNotify,
} from 'react-admin';
import { useState } from 'react';

const SPLIT_STRATEGY_CHOICES = [
  { id: 'none', name: 'None (Single Packer)' },
  { id: 'fifty_fifty', name: '50/50 Split' },
  { id: 'round_robin', name: 'Round Robin' },
  { id: 'by_category', name: 'By Category' },
];

const combinedOrderFilters = [
  <ReferenceInput source="program" reference="programs" key="program">
    <SelectInput optionText="name" />
  </ReferenceInput>,
  <SelectInput source="split_strategy" choices={SPLIT_STRATEGY_CHOICES} key="strategy" />,
];

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <CreateButton />
    <ExportButton />
  </TopToolbar>
);

export const CombinedOrderList = () => (
  <List
    filters={combinedOrderFilters}
    actions={<ListActions />}
    sort={{ field: 'created_at', order: 'DESC' }}
  >
    <Datagrid rowClick="show">
      <TextField source="name" />
      <ReferenceField source="program" reference="programs" link="show">
        <TextField source="name" />
      </ReferenceField>
      <NumberField source="order_count" label="Orders" />
      <TextField source="split_strategy" label="Strategy" />
      <TextField source="week" />
      <TextField source="year" />
      <DateField source="created_at" label="Created" />
      <EditButton />
      <ShowButton />
    </Datagrid>
  </List>
);

const CombinedOrderTitle = () => {
  const record = useRecordContext();
  return <span>Combined Order: {record?.name || `Week ${record?.week}`}</span>;
};

// Print Button Component
const PrintSummaryButton = () => {
  const record = useRecordContext();
  const dataProvider = useDataProvider();
  const notify = useNotify();
  const [loading, setLoading] = useState(false);

  if (!record) return null;

  const handlePrint = async () => {
    setLoading(true);
    try {
      // Fetch summarized items and open print dialog
      const { data } = await dataProvider.getOne('combined-orders', {
        id: `${record.id}/summarized_items`,
      });
      
      // Create printable content
      const printWindow = window.open('', '_blank');
      if (printWindow) {
        printWindow.document.write(`
          <html>
            <head>
              <title>Combined Order Summary - ${record.name || `Week ${record.week}`}</title>
              <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                h1 { color: #333; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f4f4f4; }
                .category { font-weight: bold; background-color: #e8e8e8; }
              </style>
            </head>
            <body>
              <h1>Combined Order Summary</h1>
              <p><strong>Program:</strong> ${record.program_name}</p>
              <p><strong>Week:</strong> ${record.week}, ${record.year}</p>
              <p><strong>Total Orders:</strong> ${record.order_count}</p>
              <table>
                <thead>
                  <tr>
                    <th>Category / Product</th>
                    <th>Quantity</th>
                  </tr>
                </thead>
                <tbody>
                  ${Object.entries(data || {}).map(([category, products]) => `
                    <tr class="category">
                      <td colspan="2">${category}</td>
                    </tr>
                    ${Object.entries(products as Record<string, number>).map(([product, qty]) => `
                      <tr>
                        <td style="padding-left: 20px;">${product}</td>
                        <td>${qty}</td>
                      </tr>
                    `).join('')}
                  `).join('')}
                </tbody>
              </table>
            </body>
          </html>
        `);
        printWindow.document.close();
        printWindow.print();
      }
    } catch (error) {
      notify('Error generating summary', { type: 'error' });
    }
    setLoading(false);
  };

  return <Button label="Print Summary" onClick={handlePrint} disabled={loading} />;
};

export const CombinedOrderShow = () => (
  <Show
    title={<CombinedOrderTitle />}
    actions={
      <TopToolbar>
        <PrintSummaryButton />
        <EditButton />
      </TopToolbar>
    }
  >
    <TabbedShowLayout>
      <TabbedShowLayout.Tab label="Summary">
        <TextField source="name" />
        <ReferenceField source="program" reference="programs">
          <TextField source="name" />
        </ReferenceField>
        <TextField source="split_strategy" label="Split Strategy" />
        <NumberField source="order_count" label="Total Orders" />
        <TextField source="week" />
        <TextField source="year" />
        <DateField source="created_at" showTime />
        <DateField source="updated_at" showTime />
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Orders">
        <ArrayField source="orders">
          <Datagrid bulkActionButtons={false}>
            <TextField source="order_number" label="Order #" />
            <TextField source="participant_name" label="Participant" />
            <TextField source="status" />
            <FunctionField
              source="total_price"
              label="Total"
              render={(record: { total_price: number }) =>
                record ? `$${Number(record.total_price).toFixed(2)}` : ''
              }
            />
          </Datagrid>
        </ArrayField>
      </TabbedShowLayout.Tab>
      <TabbedShowLayout.Tab label="Packing Lists">
        <ArrayField source="packing_lists">
          <Datagrid bulkActionButtons={false}>
            <TextField source="packer_name" label="Packer" />
            <NumberField source="order_count" label="Orders" />
            <ArrayField source="category_names">
              <FunctionField
                render={(record: string[]) => record?.join(', ') || '-'}
              />
            </ArrayField>
          </Datagrid>
        </ArrayField>
      </TabbedShowLayout.Tab>
    </TabbedShowLayout>
  </Show>
);

export const CombinedOrderEdit = () => (
  <Edit title={<CombinedOrderTitle />}>
    <SimpleForm>
      <TextInput source="name" />
      <ReferenceInput source="program" reference="programs" disabled>
        <SelectInput optionText="name" />
      </ReferenceInput>
      <SelectInput source="split_strategy" choices={SPLIT_STRATEGY_CHOICES} />
    </SimpleForm>
  </Edit>
);

export const CombinedOrderCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" />
      <ReferenceInput source="program" reference="programs" required>
        <SelectInput optionText="name" />
      </ReferenceInput>
      <SelectInput
        source="split_strategy"
        choices={SPLIT_STRATEGY_CHOICES}
        defaultValue="none"
      />
    </SimpleForm>
  </Create>
);
