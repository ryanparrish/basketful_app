/**
 * Order History Page
 * Displays list of past orders
 */
import React from 'react';
import {
  Box,
  Container,
  Typography,
  Alert,
  CircularProgress,
  Button,
  Paper,
} from '@mui/material';
import { ShoppingBag, Refresh } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { getOrders } from '../../shared/api/endpoints';
import { OrderCard } from './OrderCard';
import { useNavigate } from 'react-router-dom';

export const OrderHistory: React.FC = () => {
  const navigate = useNavigate();

  const {
    data: orders = [],
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['orders'],
    queryFn: getOrders,
    staleTime: 30 * 1000, // 30 seconds
  });

  const handleRefresh = () => {
    refetch();
  };

  const handleBrowseProducts = () => {
    navigate('/products');
  };

  return (
    <Container maxWidth="md" sx={{ py: 3, pb: 10 }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            My Orders
          </Typography>
          <Typography variant="body2" color="text.secondary">
            View your order history
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={isFetching ? <CircularProgress size={16} /> : <Refresh />}
          onClick={handleRefresh}
          disabled={isFetching}
        >
          Refresh
        </Button>
      </Box>

      {/* Loading State */}
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Error State */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load orders. Please try again.
        </Alert>
      )}

      {/* Empty State */}
      {!isLoading && !error && orders.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <ShoppingBag sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            No orders yet
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            You haven't placed any orders yet. Start shopping to see your orders here.
          </Typography>
          <Button
            variant="contained"
            onClick={handleBrowseProducts}
            size="large"
          >
            Browse Products
          </Button>
        </Paper>
      )}

      {/* Orders List */}
      {!isLoading && orders.length > 0 && (
        <Box>
          {orders.map((order) => (
            <OrderCard key={order.id} order={order} />
          ))}
        </Box>
      )}
    </Container>
  );
};

export default OrderHistory;
