/**
 * Order Card Details
 * The expanded part of an OrderCard: the order's items and notes. The order
 * list only carries item totals, so this loads the full order the first time
 * a card is opened (#129).
 */
import React from 'react';
import {
  Typography,
  List,
  ListItem,
  ListItemText,
  Divider,
  CircularProgress,
  Alert,
  Box,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { getOrder } from '../../shared/api/endpoints';
import { useFormatters } from '../../shared/hooks/useFormatters';

interface OrderCardDetailsProps {
  orderId: number;
}

export const OrderCardDetails: React.FC<OrderCardDetailsProps> = ({ orderId }) => {
  const { t } = useTranslation();
  const { formatCurrency } = useFormatters();
  const { data: order, isLoading, isError } = useQuery({
    queryKey: ['orders', orderId],
    queryFn: () => getOrder(orderId),
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
        <CircularProgress size={24} aria-label={t('orders.detailsLoading')} />
      </Box>
    );
  }

  if (isError || !order) {
    return <Alert severity="error">{t('orders.detailsLoadFailed')}</Alert>;
  }

  return (
    <>
      <Typography variant="subtitle2" gutterBottom>
        {t('orders.itemsHeading')}
      </Typography>
      <List disablePadding dense>
        {order.items.map((item) => (
          <ListItem key={item.id} disableGutters>
            <ListItemText
              primary={item.product_name || t('orders.productFallback', { id: item.product_id || item.product })}
              secondary={t('checkout.quantity', { count: item.quantity })}
            />
            <Typography variant="body2">
              {formatCurrency(Number(item.price) * item.quantity)}
            </Typography>
          </ListItem>
        ))}
      </List>

      {order.notes && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" gutterBottom>
            {t('orders.notesHeading')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {order.notes}
          </Typography>
        </>
      )}
    </>
  );
};

export default OrderCardDetails;
