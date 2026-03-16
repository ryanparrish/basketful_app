/**
 * PrintPackingList — print-optimized view of a packing list.
 * Mirrors PackingListAdmin.print_packing_list from apps/orders/admin.py
 */
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, CircularProgress, Typography, Box } from '@mui/material';
import PrintIcon from '@mui/icons-material/Print';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface OrderItem {
  product_name: string;
  product_category: string;
  quantity: number;
  price: number | string;
  total: number | string;
  category_sort_order: number;
  product_sort_order: number;
}

interface Order {
  id: number;
  order_number: string;
  participant_name: string;
  participant_customer_number: string;
  items: OrderItem[];
}

interface PackingListData {
  id: number;
  packer_name: string;
  category_names: string[];
  orders: number[];
  combined_order: number;
}

export const PrintPackingList = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [packingList, setPackingList] = useState<PackingListData | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = localStorage.getItem('accessToken');
        const headers = { Authorization: `Bearer ${token}` };

        const plRes = await fetch(`${API_URL}/api/v1/packing-lists/${id}/`, { headers });
        if (!plRes.ok) throw new Error('Failed to load packing list');
        const plData: PackingListData = await plRes.json();
        setPackingList(plData);

        // Fetch each order's full details
        const orderResults = await Promise.all(
          plData.orders.map((orderId) =>
            fetch(`${API_URL}/api/v1/orders/${orderId}/`, { headers }).then((r) => r.json())
          )
        );
        setOrders(orderResults);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [id]);

  if (isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
        <CircularProgress />
      </Box>
    );
  if (error) return <Box sx={{ p: 4 }}><Typography color="error">{error}</Typography></Box>;
  if (!packingList) return null;

  return (
    <>
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { font-family: Arial, sans-serif; font-size: 12px; margin: 0; }
          table { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
          th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; }
          th { background: #f0f0f0; }
          .order-block { page-break-inside: avoid; margin-bottom: 24px; }
          h2, h3 { margin: 4px 0; }
        }
      `}</style>

      {/* Toolbar — hidden when printing */}
      <Box
        className="no-print"
        sx={{ p: 2, display: 'flex', gap: 1, borderBottom: '1px solid #e0e0e0', mb: 2 }}
      >
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(`/packing-lists/${id}/show`)}
        >
          Back
        </Button>
        <Button
          variant="contained"
          startIcon={<PrintIcon />}
          onClick={() => window.print()}
        >
          Print
        </Button>
      </Box>

      <Box sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom>
          Packing List — {packingList.packer_name}
        </Typography>
        <Typography variant="body1" gutterBottom>
          <strong>Categories:</strong>{' '}
          {packingList.category_names.length > 0
            ? packingList.category_names.join(', ')
            : 'All categories'}
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {orders.length} orders &nbsp;|&nbsp; Printed: {new Date().toLocaleString()}
        </Typography>

        {orders.map((order) => {
          // Sort items by warehouse pick sequence
          const sortedItems = [...(order.items || [])].sort((a, b) => {
            const catDiff = (a.category_sort_order ?? 0) - (b.category_sort_order ?? 0);
            if (catDiff !== 0) return catDiff;
            return (a.product_sort_order ?? 0) - (b.product_sort_order ?? 0);
          });

          // Group into runs by category to emit sub-header rows
          const rows: React.ReactNode[] = [];
          let lastCategory = '';
          sortedItems.forEach((item, i) => {
            if (item.product_category !== lastCategory) {
              lastCategory = item.product_category;
              rows.push(
                <tr key={`cat-${item.product_category}-${i}`}>
                  <td
                    colSpan={4}
                    style={{
                      fontWeight: 'bold',
                      background: '#e8e8e8',
                      paddingTop: 6,
                      paddingBottom: 6,
                      fontSize: '0.85em',
                      letterSpacing: '0.05em',
                      textTransform: 'uppercase',
                    }}
                  >
                    {item.product_category}
                  </td>
                </tr>
              );
            }
            rows.push(
              <tr key={i}>
                <td style={{ paddingLeft: 16 }}>{item.product_name}</td>
                <td style={{ textAlign: 'right' }}>{item.quantity}</td>
                <td style={{ textAlign: 'right' }}>${Number(item.price).toFixed(2)}</td>
                <td style={{ textAlign: 'right' }}>${Number(item.total).toFixed(2)}</td>
              </tr>
            );
          });

          return (
            <Box key={order.id} className="order-block" sx={{ mt: 3, mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Order #{order.order_number} — Customer #{order.participant_customer_number}
              </Typography>
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th style={{ textAlign: 'right' }}>Qty</th>
                    <th style={{ textAlign: 'right' }}>Unit Price</th>
                    <th style={{ textAlign: 'right' }}>Total</th>
                  </tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </Box>
          );
        })}
      </Box>
    </>
  );
};

export default PrintPackingList;
