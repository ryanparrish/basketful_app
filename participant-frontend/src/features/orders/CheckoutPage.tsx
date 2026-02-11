/**
 * Checkout Page
 * Final order review and submission
 */
import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  CircularProgress,
  Divider,
  Stack,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
} from '@mui/material';
import {
  CheckCircle,
  ArrowBack,
  ShoppingBag,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useCartContext } from '../../providers/CartProvider';
import { useCanCheckout, useValidation } from '../../providers/ValidationContext';
import { ValidationFeedback } from '../cart/ValidationFeedback';
import { createOrder } from '../../shared/api/endpoints';
import type { CartItemData } from '../../providers/CartProvider';
import { MAX_WIDTHS, PAGE_PADDING, useFullWidth } from '../../shared/constants/layout';

export const CheckoutPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { items, cartTotal, clearCart, getApiCartItems } = useCartContext();
  const { canCheckout, checkoutBlockedReason, balances, programConfig } = useCanCheckout();
  const { revalidate } = useValidation();

  const [orderSuccess, setOrderSuccess] = useState(false);
  const [orderId, setOrderId] = useState<number | null>(null);

  // Order submission mutation
  const submitMutation = useMutation({
    mutationFn: () => createOrder({ items: getApiCartItems() }),
    onSuccess: (response) => {
      setOrderSuccess(true);
      setOrderId(response.id);
      clearCart();
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      queryClient.invalidateQueries({ queryKey: ['balances'] });
    },
    onError: (error) => {
      console.error('Order submission failed:', error);
      // Revalidate cart in case rules changed
      revalidate();
    },
  });

  const handleSubmitOrder = () => {
    if (!canCheckout) return;
    submitMutation.mutate();
  };

  const handleBackToProducts = () => {
    navigate('/products');
  };

  const handleViewOrders = () => {
    navigate('/orders');
  };

  // Order success view
  if (orderSuccess) {
    return (
      <Box sx={{ 
        ...useFullWidth(),
        py: 4,
        px: PAGE_PADDING.x,
        maxWidth: MAX_WIDTHS.FORM,
        mx: 'auto'
      }}>
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CheckCircle color="success" sx={{ fontSize: 80, mb: 2 }} />
          <Typography variant="h4" gutterBottom>
            Order Placed!
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            Your order #{orderId} has been submitted successfully.
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            You will receive a confirmation soon.
          </Typography>
          <Stack spacing={2} sx={{ mt: 4 }}>
            <Button
              variant="contained"
              size="large"
              onClick={handleViewOrders}
              startIcon={<ShoppingBag />}
            >
              View My Orders
            </Button>
            <Button
              variant="outlined"
              onClick={handleBackToProducts}
            >
              Continue Shopping
            </Button>
          </Stack>
        </Paper>
      </Box>
    );
  }

  // Empty cart check
  if (items.length === 0) {
    return (
      <Box sx={{ 
        ...useFullWidth(),
        py: 4,
        px: PAGE_PADDING.x,
        maxWidth: MAX_WIDTHS.FORM,
        mx: 'auto'
      }}>
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <ShoppingBag sx={{ fontSize: 80, color: 'text.disabled', mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            Your cart is empty
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            Add some products before checking out.
          </Typography>
          <Button
            variant="contained"
            onClick={handleBackToProducts}
            startIcon={<ArrowBack />}
          >
            Browse Products
          </Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ 
      ...useFullWidth(),
      py: PAGE_PADDING.y,
      pb: PAGE_PADDING.bottom,
      px: PAGE_PADDING.x,
    }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => navigate(-1)}
          sx={{ mb: 2 }}
        >
          Back
        </Button>
        <Typography variant="h4" component="h1" gutterBottom>
          Checkout
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Review your order before submitting
        </Typography>
      </Box>

      {/* Order Window Status */}
      {!programConfig?.order_window_open && (
        <Alert severity="error" sx={{ mb: 3 }}>
          The order window is currently closed. You cannot submit orders at this time.
        </Alert>
      )}

      {/* Validation Feedback */}
      <Box sx={{ mb: 3 }}>
        <ValidationFeedback showSuccess />
      </Box>

      {/* Order Summary */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Order Summary
          </Typography>
          <List disablePadding>
            {items.map((item: CartItemData) => (
              <ListItem key={item.id} disableGutters sx={{ py: 1 }}>
                <ListItemAvatar>
                  <Avatar variant="rounded" src={item.image}>
                    {item.name.charAt(0)}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={item.name}
                  secondary={`Qty: ${item.quantity || 1}`}
                />
                <Typography variant="body1" fontWeight={500}>
                  ${((item.price || 0) * (item.quantity || 1)).toFixed(2)}
                </Typography>
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      {/* Totals */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack spacing={1}>
            <Stack direction="row" justifyContent="space-between">
              <Typography color="text.secondary">Items:</Typography>
              <Typography>{items.length}</Typography>
            </Stack>
            {balances && (
              <>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Current Budget:</Typography>
                  <Typography>${balances.total_budget.toFixed(2)}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography color="text.secondary">Already Used:</Typography>
                  <Typography>${balances.used_budget.toFixed(2)}</Typography>
                </Stack>
              </>
            )}
            <Divider sx={{ my: 1 }} />
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="h6">Order Total:</Typography>
              <Typography variant="h6" color="primary" fontWeight={600}>
                ${cartTotal.toFixed(2)}
              </Typography>
            </Stack>
            {balances && (
              <Stack direction="row" justifyContent="space-between">
                <Typography color="text.secondary">Remaining After Order:</Typography>
                <Typography
                  color={balances.remaining_budget - cartTotal < 0 ? 'error.main' : 'success.main'}
                  fontWeight={500}
                >
                  ${(balances.remaining_budget - cartTotal).toFixed(2)}
                </Typography>
              </Stack>
            )}
          </Stack>
        </CardContent>
      </Card>

      {/* Error Display */}
      {submitMutation.isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {submitMutation.error instanceof Error
            ? submitMutation.error.message
            : 'Failed to submit order. Please try again.'}
        </Alert>
      )}

      {/* Submit Button */}
      <Box sx={{ display: 'flex', gap: 2, flexDirection: 'column' }}>
        <Button
          variant="contained"
          size="large"
          onClick={handleSubmitOrder}
          disabled={!canCheckout || submitMutation.isPending}
          sx={{ py: 2 }}
        >
          {submitMutation.isPending ? (
            <>
              <CircularProgress size={24} sx={{ mr: 1 }} color="inherit" />
              Submitting Order...
            </>
          ) : canCheckout ? (
            'Submit Order'
          ) : (
            checkoutBlockedReason || 'Cannot Submit'
          )}
        </Button>

        <Button
          variant="outlined"
          onClick={handleBackToProducts}
          disabled={submitMutation.isPending}
        >
          Continue Shopping
        </Button>
      </Box>
    </Box>
  );
};

export default CheckoutPage;
