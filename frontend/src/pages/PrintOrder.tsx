/**
 * PrintOrder — print-optimized view of a single order.
 * Mirrors OrderAdmin.print_order from apps/orders/admin.py
 */
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, CircularProgress, Typography, Box } from '@mui/material';
import PrintIcon from '@mui/icons-material/Print';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import apiClient from '../lib/api/apiClient.ts';

interface OrderItem {
  product_name: string;
  product_category: string;
  product_subcategory?: string | null;
  quantity: number;
  price: number | string;
  total: number | string;
  // Sort order fields from OrderItemSerializer — used to match packing list order
  category_sort_order?: number;
  subcategory_sort_order?: number;
  product_sort_order?: number;
}

interface Order {
  id: number;
  order_number: string;
  participant_name: string;
  participant_customer_number: string;
  program_name: string;
  status: string;
  total_price: number | string;
  go_fresh_total: number | string;
  order_date: string;
  items: OrderItem[];
}

export const PrintOrder = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchOrder = async () => {
      try {
        const res = await apiClient.get(`/orders/${id}/`);
        setOrder(res.data);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setIsLoading(false);
      }
    };
    fetchOrder();
  }, [id]);

  if (isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
        <CircularProgress />
      </Box>
    );
  if (error) return <Box sx={{ p: 4 }}><Typography color="error">{error}</Typography></Box>;
  if (!order) return null;

  return (
    <>
      <style>{`
        @media print {
          /* Hide React-Admin layout elements */
          .no-print { display: none !important; }
          .RaLayout-appFrame { margin-left: 0 !important; }
          .RaSidebar-root, .RaAppBar-root, .RaLayout-sidebar, .MuiDrawer-root { 
            display: none !important; 
          }
          .RaLayout-content, .RaLayout-contentWithSidebar {
            margin-left: 0 !important;
            margin-top: 0 !important;
            padding: 0 !important;
          }
          
          body, html { 
            font-family: Arial, sans-serif; 
            font-size: 12px; 
            margin: 0 !important;
            padding: 0 !important;
          }
          #root, #root > div {
            margin: 0 !important;
            padding: 0 !important;
          }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; }
          th { background: #f0f0f0; }
          tfoot td { font-weight: bold; background: #f9f9f9; }
          h2 { margin: 4px 0 12px; }
        }
      `}</style>

      {/* Toolbar */}
      <Box
        className="no-print"
        sx={{ p: 2, display: 'flex', gap: 1, borderBottom: '1px solid #e0e0e0', mb: 2 }}
      >
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(`/orders/${id}/show`)}
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
          Order #{order.order_number}
        </Typography>

        {/* Order meta */}
        <Box sx={{ display: 'flex', gap: 4, mb: 3, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="body2">
              <strong>Participant:</strong> {order.participant_name}
            </Typography>
            <Typography variant="body2">
              <strong>Customer #:</strong> {order.participant_customer_number}
            </Typography>
            <Typography variant="body2">
              <strong>Program:</strong> {order.program_name}
            </Typography>
          </Box>
          <Box>
            <Typography variant="body2">
              <strong>Status:</strong> {order.status?.toUpperCase()}
            </Typography>
            <Typography variant="body2">
              <strong>Order Date:</strong>{' '}
              {order.order_date ? new Date(order.order_date).toLocaleDateString() : '—'}
            </Typography>
            <Typography variant="body2">
              <strong>Total:</strong> ${Number(order.total_price).toFixed(2)}
            </Typography>
          </Box>
        </Box>

        {/* Items table — sorted by category → subcategory → product sort_order
             to match the packing list display order */}
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Category</th>
              <th style={{ textAlign: 'right' }}>Qty</th>
              <th style={{ textAlign: 'right' }}>Unit Price</th>
              <th style={{ textAlign: 'right' }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {[...(order.items || [])]
              .sort((a, b) => {
                const catDiff = (a.category_sort_order ?? 0) - (b.category_sort_order ?? 0);
                if (catDiff !== 0) return catDiff;
                const subDiff = (a.subcategory_sort_order ?? 9999) - (b.subcategory_sort_order ?? 9999);
                if (subDiff !== 0) return subDiff;
                return (a.product_sort_order ?? 0) - (b.product_sort_order ?? 0);
              })
              .map((item, i) => (
              <tr key={i}>
                <td>{item.product_name}</td>
                <td>{item.product_category}</td>
                <td style={{ textAlign: 'right' }}>{item.quantity}</td>
                <td style={{ textAlign: 'right' }}>${Number(item.price).toFixed(2)}</td>
                <td style={{ textAlign: 'right' }}>${Number(item.total).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={4} style={{ textAlign: 'right' }}>Total:</td>
              <td style={{ textAlign: 'right' }}>${Number(order.total_price).toFixed(2)}</td>
            </tr>
          </tfoot>
        </table>

        <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
          Printed: {new Date().toLocaleString()}
        </Typography>
      </Box>
    </>
  );
};

export default PrintOrder;
