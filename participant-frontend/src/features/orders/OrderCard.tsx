/**
 * Order Card Component
 * Displays a single order with expandable details
 */
import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Collapse,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Divider,
  Stack,
} from '@mui/material';
import {
  ExpandMore,
  ExpandLess,
  Schedule,
  CheckCircle,
  LocalShipping,
  Cancel,
  Pending,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { Order, OrderListItem } from '../../shared/types/api';
import { useFormatters } from '../../shared/hooks/useFormatters';
import { translateDynamic } from '../../i18n';

interface OrderCardProps {
  order: Order | OrderListItem;
}

type StatusChipColor = 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';

const STATUS_CONFIGS: Record<string, { color: StatusChipColor; icon: React.ReactNode }> = {
  pending: { color: 'warning', icon: <Pending /> },
  confirmed: { color: 'info', icon: <Schedule /> },
  processing: { color: 'primary', icon: <Schedule /> },
  shipped: { color: 'secondary', icon: <LocalShipping /> },
  delivered: { color: 'success', icon: <CheckCircle /> },
  completed: { color: 'success', icon: <CheckCircle /> },
  cancelled: { color: 'error', icon: <Cancel /> },
};

export const OrderCard: React.FC<OrderCardProps> = ({ order }) => {
  const { t } = useTranslation();
  const { formatCurrency, formatDate, formatTime } = useFormatters();
  const [expanded, setExpanded] = useState(false);

  const statusKey = order.status?.toLowerCase();
  const statusConfig = STATUS_CONFIGS[statusKey] || { color: 'default' as StatusChipColor, icon: <Pending /> };
  // Status labels are keyed by the backend status code; an unknown status
  // falls back to displaying the raw code
  const statusLabel = translateDynamic(`orders.status.${statusKey}`, {
    defaultValue: order.status,
  });
  const orderDate = new Date(order.created_at || order.order_date);
  const formattedDate = formatDate(orderDate);
  const formattedTime = formatTime(orderDate);

  const itemCount = order.items?.length || 0;
  const totalQuantity = order.items?.reduce((sum, item) => sum + item.quantity, 0) || 0;

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        {/* Header Row */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            mb: 1,
          }}
        >
          <Box>
            <Typography variant="subtitle1" fontWeight={600}>
              {t('orders.orderNumber', { id: order.id })}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t('orders.dateAtTime', { date: formattedDate, time: formattedTime })}
            </Typography>
          </Box>
          <Chip
            icon={statusConfig.icon as React.ReactElement}
            label={statusLabel}
            color={statusConfig.color}
            size="small"
          />
        </Box>

        {/* Summary Row */}
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{ mt: 2 }}
        >
          <Typography variant="body2" color="text.secondary">
            {t('orders.itemsSummary', { count: itemCount, total: totalQuantity })}
          </Typography>
          <Typography variant="h6" color="primary" fontWeight={600}>
            {formatCurrency(order.total || order.total_price)}
          </Typography>
        </Stack>

        {/* Expand Button */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
          <IconButton
            onClick={() => setExpanded(!expanded)}
            size="small"
            aria-expanded={expanded}
            aria-label={expanded ? t('orders.showLess') : t('orders.showDetails')}
          >
            {expanded ? <ExpandLess /> : <ExpandMore />}
          </IconButton>
        </Box>

        {/* Expanded Details */}
        <Collapse in={expanded}>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" gutterBottom>
            {t('orders.itemsHeading')}
          </Typography>
          <List disablePadding dense>
            {order.items?.map((item, idx) => (
              <ListItem key={idx} disableGutters>
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
        </Collapse>
      </CardContent>
    </Card>
  );
};

export default OrderCard;
