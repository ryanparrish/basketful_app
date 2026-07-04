import {
  List,
  Datagrid,
  TextField,
  DateField,
  ReferenceArrayField,
  SingleFieldList,
  ChipField,
  Show,
  SimpleShowLayout,
  Create,
  SimpleForm,
  TextInput,
  ReferenceArrayInput,
  SelectArrayInput,
  FunctionField,
  useRecordContext,
  TopToolbar,
  Button,
  useNotify,
  ListButton,
  useRefresh,
  useDataProvider,
  type RaRecord,
} from 'react-admin';
import { Typography, Box, Chip, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { API_URL } from '../utils/apiUrl';

const DownloadWarehouseInventoryPdfButton = () => {
  const record = useRecordContext();
  const notify = useNotify();

  if (!record) return null;

  const handleDownload = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      const response = await fetch(
        `${API_URL}/api/v1/warehouse-inventory-lists/${record.id}/download-pdf/`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Download failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `warehouse_inventory_${record.id}_${record.name?.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      notify('PDF downloaded successfully', { type: 'success' });
    } catch {
      notify('Error downloading PDF', { type: 'error' });
    }
  };

  return (
    <Button label="Download PDF" onClick={handleDownload}>
      <DownloadIcon />
    </Button>
  );
};

const RefreshSummaryButton = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();

  if (!record) return null;

  const handleRefresh = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      await fetch(
        `${API_URL}/api/v1/warehouse-inventory-lists/${record.id}/refresh-summary/`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );
      notify('Summary refreshed successfully', { type: 'success' });
      refresh();
    } catch {
      notify('Error refreshing summary', { type: 'error' });
    }
  };

  return (
    <Button label="Refresh Summary" onClick={handleRefresh}>
      <RefreshIcon />
    </Button>
  );
};

const WarehouseInventoryListShowActions = () => (
  <TopToolbar>
    <ListButton />
    <RefreshSummaryButton />
    <DownloadWarehouseInventoryPdfButton />
  </TopToolbar>
);

const SummarizedProductsField = () => {
  const record = useRecordContext();
  if (!record?.summarized_data) return <Typography>No data available. Click "Refresh Summary".</Typography>;

  const data = record.summarized_data;

  return (
    <Box>
      {Object.entries(data).map(([category, products]: [string, any]) => (
        <Accordion key={category} defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6">
              {category} ({Object.keys(products).length} items)
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {Object.entries(products).map(([product, quantity]: [string, any]) => (
                <Chip
                  key={product}
                  label={`${product}: ${quantity}`}
                  variant="outlined"
                  size="small"
                />
              ))}
            </Box>
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );
};

export const WarehouseInventoryListList = () => (
  <List>
    <Datagrid rowClick="show">
      <TextField source="name" />
      <FunctionField
        label="Programs"
        render={(record: RaRecord) => record.combined_order_count || 0}
      />
      <DateField source="created_at" showTime />
      <FunctionField
        label="Actions"
        render={(record: RaRecord) => (
          <Button
            component="a"
            href={`${API_URL}/api/v1/warehouse-inventory-lists/${record.id}/download-pdf/`}
            target="_blank"
            label="PDF"
          >
            <DownloadIcon />
          </Button>
        )}
      />
    </Datagrid>
  </List>
);

export const WarehouseInventoryListShow = () => (
  <Show actions={<WarehouseInventoryListShowActions />}>
    <SimpleShowLayout>
      <TextField source="name" />
      
      <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
        Combined Orders ({useRecordContext()?.combined_order_count || 0})
      </Typography>
      <ReferenceArrayField source="combined_orders" reference="combined-orders">
        <SingleFieldList>
          <ChipField source="name" />
        </SingleFieldList>
      </ReferenceArrayField>
      
      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />

      <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
        Aggregated Products
      </Typography>
      <SummarizedProductsField />
    </SimpleShowLayout>
  </Show>
);

export const WarehouseInventoryListCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput 
        source="name" 
        label="List Name" 
        required 
        helperText="E.g., 'Tuesday/Wednesday Packing Run' or 'Week 12 Bulk Order'"
      />
      <ReferenceArrayInput 
        source="combined_orders" 
        reference="combined-orders"
        label="Select Combined Orders"
        helperText="Select the combined orders to aggregate into this shopping list"
      >
        <SelectArrayInput optionText="name" />
      </ReferenceArrayInput>
    </SimpleForm>
  </Create>
);
