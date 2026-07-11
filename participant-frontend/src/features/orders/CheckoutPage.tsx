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
import { useTranslation } from 'react-i18next';
import { useCartContext } from '../../providers/CartProvider';
import { useCanCheckout, useValidation } from '../../providers/ValidationContext';
import { ValidationFeedback } from '../cart/ValidationFeedback';
import { createOrder } from '../../shared/api/endpoints';
import { useOrderWindow } from '../../shared/hooks/useOrderWindow';
import { useFormatters } from '../../shared/hooks/useFormatters';
import type { CartItemData } from '../../providers/CartProvider';
import { MAX_WIDTHS, PAGE_PADDING, useFullWidth } from '../../shared/constants/layout';

export const CheckoutPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const { formatCurrency } = useFormatters();
  const { items, cartTotal, clearCart, getApiCartItems } = useCartContext();
  const { canCheckout, checkoutBlockedReasonKey, balances } = useCanCheckout();
  const { isOpen: windowIsOpen, windowStatus } = useOrderWindow();
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
            {t('checkout.orderPlaced')}
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            {t('checkout.orderSubmitted', { orderId })}
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            {t('checkout.confirmationSoon')}
          </Typography>
          <Stack spacing={2} sx={{ mt: 4 }}>
            <Button
              variant="contained"
              size="large"
              onClick={handleViewOrders}
              startIcon={<ShoppingBag />}
            >
              {t('checkout.viewMyOrders')}
            </Button>
            <Button
              variant="outlined"
              onClick={handleBackToProducts}
            >
              {t('common.continueShopping')}
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
            {t('checkout.emptyTitle')}
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            {t('checkout.emptySubtitle')}
          </Typography>
          <Button
            variant="contained"
            onClick={handleBackToProducts}
            startIcon={<ArrowBack />}
          >
            {t('common.browseProducts')}
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
          {t('common.back')}
        </Button>
        <Typography variant="h4" component="h1" gutterBottom>
          {t('checkout.title')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {t('checkout.subtitle')}
        </Typography>
      </Box>

      {/* Order Window Status */}
      {!windowIsOpen && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {windowStatus === 'force_closed'
            ? t('checkout.windowForceClosed')
            : windowStatus === 'no_schedule'
            ? t('checkout.windowNoSchedule')
            : windowStatus === 'paused'
            ? t('checkout.windowPaused')
            : t('checkout.windowClosed')}
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
            {t('checkout.orderSummary')}
          </Typography>
          <List disablePadding>
            {items.map((item: CartItemData) => (
              <ListItem key={item.id} disableGutters sx={{ py: 1 }}>
                <ListItemAvatar>
                  <Avatar variant="rounded" src={item.image?.replace(/^http:/, 'https:')}>
                    {item.name.charAt(0)}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={item.name}
                  secondary={t('checkout.quantity', { count: item.quantity || 1 })}
                />
                <Typography variant="body1" fontWeight={500}>
                  {formatCurrency((item.price || 0) * (item.quantity || 1))}
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
              <Typography color="text.secondary">{t('checkout.itemsLabel')}</Typography>
              <Typography>{items.length}</Typography>
            </Stack>
            {balances && (
              <Stack direction="row" justifyContent="space-between">
                <Typography color="text.secondary">{t('checkout.availableBudget')}</Typography>
                <Typography>{formatCurrency(balances.available_balance)}</Typography>
              </Stack>
            )}
            <Divider sx={{ my: 1 }} />
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="h6">{t('checkout.orderTotal')}</Typography>
              <Typography variant="h6" color="primary" fontWeight={600}>
                {formatCurrency(cartTotal)}
              </Typography>
            </Stack>
            {balances && (
              <Stack direction="row" justifyContent="space-between">
                <Typography color="text.secondary">{t('checkout.remainingAfterOrder')}</Typography>
                <Typography
                  color={balances.available_balance - cartTotal < 0 ? 'error.main' : 'success.main'}
                  fontWeight={500}
                >
                  {formatCurrency(balances.available_balance - cartTotal)}
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
            : t('checkout.submitFailed')}
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
              {t('checkout.submitting')}
            </>
          ) : canCheckout ? (
            t('checkout.submitOrder')
          ) : checkoutBlockedReasonKey ? (
            t(checkoutBlockedReasonKey)
          ) : (
            t('checkout.cannotSubmit')
          )}
        </Button>

        <Button
          variant="outlined"
          onClick={handleBackToProducts}
          disabled={submitMutation.isPending}
        >
          {t('common.continueShopping')}
        </Button>
      </Box>
    </Box>
  );
};

export default CheckoutPage;
