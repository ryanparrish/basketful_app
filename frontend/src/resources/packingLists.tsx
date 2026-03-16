import {
  List,
  Datagrid,
  TextField,
  DateField,
  ReferenceField,
  Show,
  SimpleShowLayout,
  FunctionField,
  useRecordContext,
  TopToolbar,
  Button,
  useNotify,
  ListButton,
  ReferenceInput,
  SelectInput,
  type RaRecord,
} from 'react-admin';
import { Card, CardContent, Typography, Box, Chip } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import PrintIcon from '@mui/icons-material/Print';
import { useNavigate } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const DownloadPackingListPdfButton = () => {
  const record = useRecordContext();
  const notify = useNotify();

  if (!record) return null;

  const handleDownload = async () => {
    try {
      const token = localStorage.getItem('accessToken');
      const response = await fetch(
        `${API_URL}/api/v1/packing-lists/${record.id}/download-pdf/`,
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
      a.download = `packing_list_${record.packer_name?.replace(/\s+/g, '_')}_${record.combined_order}.pdf`;
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

const PackingListShowActions = () => {
  const record = useRecordContext();
  const navigate = useNavigate();
  return (
    <TopToolbar>
      <ListButton />
      <Button
        label="Print"
        onClick={() => navigate(`/packing-lists/${record?.id}/print`)}
        disabled={!record}
      >
        <PrintIcon />
      </Button>
      <DownloadPackingListPdfButton />
    </TopToolbar>
  );
};

const packingListFilters = [
  <ReferenceInput source="packer" reference="order-packers" key="packer">
    <SelectInput optionText="name" label="Packer" />
  </ReferenceInput>,
  <ReferenceInput source="combined_order" reference="combined-orders" key="combined_order">
    <SelectInput optionText="name" label="Combined Order" />
  </ReferenceInput>,
];

const OrdersField = () => {
  const record = useRecordContext();
  const navigate = useNavigate();
  if (!record) return null;

  // Prefer rich summary data from orders_summary; fall back to raw IDs
  const summary: Array<{ id: number; order_number: string; customer_number: string }> =
    record.orders_summary || [];
  const total = record.orders?.length || 0;
  const displaying = summary.slice(0, 10);

  if (summary.length > 0) {
    return (
      <Box>
        {displaying.map((o) => (
          <Box key={o.id} sx={{ mb: 0.5 }}>
            <Button
              label={`#${o.order_number} – Customer #${o.customer_number}`}
              onClick={() => navigate(`/orders/${o.id}/show`)}
              size="small"
            />
          </Box>
        ))}
        {total > 10 && (
          <Typography variant="body2" sx={{ mt: 1 }}>
            … and {total - 10} more
          </Typography>
        )}
      </Box>
    );
  }

  // Fallback: raw IDs
  return (
    <Box>
      {(record.orders || []).slice(0, 10).map((orderId: number) => (
        <Chip key={orderId} label={`Order #${orderId}`} size="small" sx={{ m: 0.5 }} />
      ))}
      {total > 10 && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          … and {total - 10} more
        </Typography>
      )}
    </Box>
  );
};

const CategoriesField = () => {
  const record = useRecordContext();
  if (!record || !record.categories) return null;

  if (record.categories.length === 0) {
    return <Typography variant="body2">All categories</Typography>;
  }

  return (
    <Box>
      {record.categories.map((category: RaRecord) => (
        <Chip
          key={category.id}
          label={category.name}
          size="small"
          sx={{ m: 0.5 }}
        />
      ))}
    </Box>
  );
};

const SummarizedDataField = () => {
  const record = useRecordContext();
  if (!record || !record.summarized_data) return null;

  const data = record.summarized_data;
  const categories = Object.keys(data);

  return (
    <Box>
      {categories.map((category) => (
        <Card key={category} sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {category}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {Object.entries(data[category]).map(([product, quantity]) => (
                <Chip
                  key={product}
                  label={`${product}: ${quantity}`}
                  variant="outlined"
                  size="small"
                />
              ))}
            </Box>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
};

export const PackingListList = () => (
  <List
    sort={{ field: 'created_at', order: 'DESC' }}
    filters={packingListFilters}
  >
    <Datagrid rowClick="show" bulkActionButtons={false}>
      <ReferenceField source="combined_order" reference="combined-orders" link="show">
        <TextField source="name" />
      </ReferenceField>
      <TextField source="packer_name" label="Packer" />
      <FunctionField
        label="Orders"
        render={(record: RaRecord) => record.orders?.length || 0}
      />
      <DateField source="created_at" showTime />
    </Datagrid>
  </List>
);

export const PackingListShow = () => (
  <Show actions={<PackingListShowActions />}>
    <SimpleShowLayout>
      <ReferenceField source="combined_order" reference="combined-orders" link="show">
        <TextField source="name" />
      </ReferenceField>
      <TextField source="packer_name" label="Packer" />
      <DateField source="created_at" showTime />
      <DateField source="updated_at" showTime />

      <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
        Assigned Categories
      </Typography>
      <CategoriesField />

      <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
        Orders ({useRecordContext()?.orders?.length || 0})
      </Typography>
      <OrdersField />

      <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
        Summarized Products
      </Typography>
      <SummarizedDataField />
    </SimpleShowLayout>
  </Show>
);
