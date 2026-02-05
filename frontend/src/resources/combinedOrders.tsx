/**
 * Combined Order Resource Components
 */
import {
  List,
  Datagrid,
  TextField,
  DateField,
  ReferenceField,
  Show,
  SimpleShowLayout,
  FilterButton,
  CreateButton,
  ExportButton,
  TopToolbar,
  useRecordContext,
  FunctionField,
  Button,
  useNotify,
  useRefresh,
  DeleteButton,
  ListButton,
  Create,
  Edit,
  SimpleForm,
  TextInput,
  SelectInput,
  ReferenceInput,
  ReferenceArrayInput,
  SelectArrayInput,
  required,
} from 'react-admin';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import { useNavigate } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SPLIT_STRATEGY_LABELS: Record<string, string> = {
  none: 'No Split (Single Packer)',
  category: 'By Category',
  subcategory: 'By Subcategory',
  category_subcategory: 'By Category & Subcategory',
};


// Download actions
const DownloadPrimaryPdfButton = () => {
  const record = useRecordContext();
  const notify = useNotify();

  if (!record) return null;

  const handleDownload = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      const response = await fetch(
        `${API_URL}/api/v1/combined-orders/${record.id}/download-primary-pdf/`,
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
      a.download = `primary_order_${record.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      notify('PDF downloaded successfully', { type: 'success' });
    } catch (error) {
      notify('Error downloading PDF', { type: 'error' });
    }
  };

  return (
    <Button label="Primary Order PDF" onClick={handleDownload}>
      <DownloadIcon />
    </Button>
  );
};

const DownloadAllPackingListsButton = () => {
  const record = useRecordContext();
  const notify = useNotify();

  if (!record) return null;

  const handleDownload = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      const response = await fetch(
        `${API_URL}/api/v1/combined-orders/${record.id}/download-all-packing-lists/`,
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
      a.download = `combined_order_${record.id}_all_lists.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      notify('ZIP downloaded successfully', { type: 'success' });
    } catch (error) {
      notify('Error downloading ZIP', { type: 'error' });
    }
  };

  return (
    <Button label="All Packing Lists (ZIP)" onClick={handleDownload}>
      <DownloadIcon />
    </Button>
  );
};

const UncombineButton = () => {
  const record = useRecordContext();
  const notify = useNotify();
  const refresh = useRefresh();
  const navigate = useNavigate();

  if (!record) return null;

  const handleUncombine = async () => {
    if (!window.confirm('Are you sure you want to uncombine this order? This will release all combined orders.')) {
      return;
    }

    try {
      const token = localStorage.getItem('accessToken');
      const response = await fetch(
        `${API_URL}/api/v1/combined-orders/${record.id}/uncombine/`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) throw new Error('Uncombine failed');

      notify('Combined order uncombined successfully', { type: 'success' });
      navigate('/combined-orders');
      refresh();
    } catch (error) {
      notify('Error uncombining order', { type: 'error' });
    }
  };

  return (
    <Button label="Uncombine" onClick={handleUncombine} color="warning">
      <UnfoldMoreIcon />
    </Button>
  );
};

const CombinedOrderShowActions = () => (
  <TopToolbar>
    <ListButton />
    <DownloadPrimaryPdfButton />
    <DownloadAllPackingListsButton />
    <UncombineButton />
    <DeleteButton mutationMode="pessimistic" />
  </TopToolbar>
);

// Split strategy display
const SplitStrategyField = () => {
  const record = useRecordContext();
  if (!record) return null;

  return (
    <Chip
      label={SPLIT_STRATEGY_LABELS[record.split_strategy] || record.split_strategy}
      color="primary"
      size="small"
    />
  );
};

// Orders display
const OrdersField = () => {
  const record = useRecordContext();
  if (!record || !record.orders) return null;

  return (
    <Box>
      {record.orders.map((orderId: number) => (
        <Chip
          key={orderId}
          label={`Order #${orderId}`}
          size="small"
          sx={{ m: 0.5 }}
        />
      ))}
    </Box>
  );
};

// Packing Lists display
const PackingListsField = () => {
  const record = useRecordContext();
  if (!record || !record.packing_lists) return null;

  if (record.packing_lists.length === 0) {
    return <Typography variant="body2">No packing lists (single packer)</Typography>;
  }

  return (
    <Box>
      {record.packing_lists.map((pl: any) => (
        <Card key={pl.id} sx={{ mb: 1 }}>
          <CardContent>
            <Typography variant="subtitle2">{pl.packer_name}</Typography>
            <Typography variant="body2" color="text.secondary">
              {pl.order_count} orders
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
};

const ListActions = () => (
  <TopToolbar>
    <FilterButton />
    <CreateButton />
    <ExportButton />
  </TopToolbar>
);

export const CombinedOrderList = () => (
  <List
    sort={{ field: 'created_at', order: 'DESC' }}
    filters={[]}
    actions={<ListActions />}
  >
    <Datagrid rowClick="show" bulkActionButtons={false}>
      <TextField source="name" />
      <ReferenceField source="program" reference="programs" link="show">
        <TextField source="name" />
      </ReferenceField>
      <FunctionField
        label="Split Strategy"
        render={() => <SplitStrategyField />}
      />
      <FunctionField
        label="Orders"
        render={(record: { orders?: unknown[] }) => record?.orders?.length || 0}
      />
      <FunctionField
        label="Packing Lists"
        render={(record: { packing_lists?: unknown[] }) => record?.packing_lists?.length || 0}
      />
      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />
    </Datagrid>
  </List>
);

export const CombinedOrderShow = () => (
  <Show actions={<CombinedOrderShowActions />}>
    <SimpleShowLayout>
      <TextField source="name" />
      <ReferenceField source="program" reference="programs" link="show">
        <TextField source="name" />
      </ReferenceField>
      <FunctionField
        label="Split Strategy"
        render={() => <SplitStrategyField />}
      />
      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />

      <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
        Orders
      </Typography>
      <OrdersField />

      <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
        Packing Lists
      </Typography>
      <PackingListsField />
    </SimpleShowLayout>
  </Show>
);

const SPLIT_STRATEGY_CHOICES = [
  { id: 'none', name: 'No Split (Single Packer)' },
  { id: 'category', name: 'By Category' },
  { id: 'subcategory', name: 'By Subcategory' },
  { id: 'category_subcategory', name: 'By Category & Subcategory' },
];

const CombinedOrderTitle = () => {
  const record = useRecordContext();
  return <span>Combined Order: {record?.name || ''}</span>;
};

export const CombinedOrderCreate = () => (
  <Create>
    <SimpleForm>
      <TextInput source="name" validate={required()} fullWidth helperText="A descriptive name for this combined order" />
      <ReferenceInput source="program" reference="programs">
        <SelectInput optionText="name" fullWidth validate={required()} />
      </ReferenceInput>
      <SelectInput 
        source="split_strategy" 
        choices={SPLIT_STRATEGY_CHOICES} 
        defaultValue="none"
        helperText="How to split orders among packers"
        fullWidth
      />
      <ReferenceArrayInput source="orders" reference="orders">
        <SelectArrayInput 
          optionText={(record: { order_number: string; participant_name: string }) => 
            `${record.order_number} - ${record.participant_name}`
          }
          fullWidth 
        />
      </ReferenceArrayInput>
    </SimpleForm>
  </Create>
);

export const CombinedOrderEdit = () => (
  <Edit title={<CombinedOrderTitle />}>
    <SimpleForm>
      <TextInput source="name" validate={required()} fullWidth />
      <ReferenceInput source="program" reference="programs">
        <SelectInput optionText="name" fullWidth disabled />
      </ReferenceInput>
      <SelectInput 
        source="split_strategy" 
        choices={SPLIT_STRATEGY_CHOICES}
        helperText="How to split orders among packers"
        fullWidth
      />
    </SimpleForm>
  </Edit>
);