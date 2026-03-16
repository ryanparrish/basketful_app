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
  ExportButton,
  TopToolbar,
  useRecordContext,
  FunctionField,
  Button,
  useNotify,
  useRefresh,
  DeleteButton,
  ListButton,
  Edit,
  SimpleForm,
  TextInput,
  SelectInput,
  ReferenceInput,
  type RaRecord,
} from 'react-admin';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import UnfoldMoreIcon from '@mui/icons-material/UnfoldMore';
import MergeTypeIcon from '@mui/icons-material/MergeType';
import { useNavigate } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Custom empty state that always shows the create button
const EmptyWithCreate = () => {
  const navigate = useNavigate();
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        py: 10,
        gap: 2,
        color: 'text.secondary',
      }}
    >
      <MergeTypeIcon sx={{ fontSize: 72, opacity: 0.4 }} />
      <Typography variant="h6" sx={{ opacity: 0.7 }}>No Combined Orders yet.</Typography>
      <Button
        variant="contained"
        label="Create Combined Order"
        onClick={() => navigate('/combined-orders/create-wizard')}
      />
    </Box>
  );
};

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
    } catch {
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
    } catch {
      notify('Error downloading ZIP', { type: 'error' });
    }
  };

  return (
    <Button label="All Packing Lists (ZIP)" onClick={handleDownload}>
      <DownloadIcon />
    </Button>
  );
};

const DownloadFirstPackingListPdfButton = () => {
  const record = useRecordContext();
  const notify = useNotify();

  if (!record) return null;

  const handleDownload = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      const response = await fetch(
        `${API_URL}/api/v1/combined-orders/${record.id}/download-packing-list-pdf/`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `packing_list_${record.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      notify('Packing list PDF downloaded', { type: 'success' });
    } catch {
      notify('Error downloading packing list PDF', { type: 'error' });
    }
  };

  return (
    <Button label="First Packing List PDF" onClick={handleDownload}>
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
    } catch {
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
    <DownloadFirstPackingListPdfButton />
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

// Orders display — shows order_number + customer_number with links
const OrdersField = () => {
  const record = useRecordContext();
  const navigate = useNavigate();
  if (!record || !record.orders) return null;

  return (
    <Box>
      {record.orders.map((order: RaRecord) => (
        <Box key={order.id} sx={{ mb: 0.5 }}>
          <Button
            label={`Order #${order.order_number} – Customer #${order.participant_customer_number || 'N/A'}`}
            onClick={() => navigate(`/orders/${order.id}/show`)}
            size="small"
          />
        </Box>
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
      {record.packing_lists.map((pl: RaRecord) => (
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

const SPLIT_STRATEGY_CHOICES = [
  { id: 'none', name: 'No Split (Single Packer)' },
  { id: 'category', name: 'By Category' },
  { id: 'subcategory', name: 'By Subcategory' },
  { id: 'category_subcategory', name: 'By Category & Subcategory' },
];

const combinedOrderFilters = [
  <ReferenceInput source="program" reference="programs" key="program">
    <SelectInput optionText="name" label="Program" />
  </ReferenceInput>,
  <SelectInput
    source="split_strategy"
    label="Split Strategy"
    choices={SPLIT_STRATEGY_CHOICES.filter((c) => c.id !== '')}
    key="strategy"
  />,
];

const ListActions = () => {
  const navigate = useNavigate();
  return (
    <TopToolbar>
      <FilterButton />
      <Button label="Create Combined Order" onClick={() => navigate('/combined-orders/create-wizard')}>
        <span style={{ fontSize: '1.2rem', lineHeight: 1 }}>+</span>
      </Button>
      <ExportButton />
    </TopToolbar>
  );
};

export const CombinedOrderList = () => (
  <List
    sort={{ field: 'created_at', order: 'DESC' }}
    filters={combinedOrderFilters}
    actions={<ListActions />}
    empty={<EmptyWithCreate />}
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

const CombinedOrderTitle = () => {
  const record = useRecordContext();
  return <span>Combined Order: {record?.name || ''}</span>;
};

export const CombinedOrderEdit = () => (
  <Edit title={<CombinedOrderTitle />}>
    <SimpleForm>
      <TextInput source="name" fullWidth helperText="Leave blank to keep the auto-generated name" />
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