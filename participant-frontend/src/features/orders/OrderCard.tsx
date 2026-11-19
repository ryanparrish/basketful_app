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
  Divider,
  Stack,
} from '@mui/material';
import {
  ExpandMore,
  ExpandLess,
  Schedule,
  CheckCircle,
  Inventory2,
  Cancel,
  Pending,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { OrderListItem } from '../../shared/types/api';
import { useFormatters } from '../../shared/hooks/useFormatters';
import { translateDynamic } from '../../i18n';
import { OrderCardDetails } from './OrderCardDetails';

interface OrderCardProps {
  order: OrderListItem;
}

type StatusChipColor = 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';

interface StatusChipConfig {
  color: StatusChipColor;
  icon: React.ReactNode;
}

// The statuses an order can actually be in (apps/orders/models.py
// Order.status choices). Keying the config by this union makes the build
// fail if a status is missing a chip.
type OrderStatus = 'pending' | 'confirmed' | 'packing' | 'completed' | 'cancelled';

const STATUS_CONFIGS: Record<OrderStatus, StatusChipConfig> = {
  pending: { color: 'warning', icon: <Pending /> },
  confirmed: { color: 'info', icon: <Schedule /> },
  packing: { color: 'primary', icon: <Inventory2 /> },
  completed: { color: 'success', icon: <CheckCircle /> },
  cancelled: { color: 'error', icon: <Cancel /> },
};

const UNKNOWN_STATUS_CONFIG: StatusChipConfig = { color: 'default', icon: <Pending /> };

export const OrderCard: React.FC<OrderCardProps> = ({ order }) => {
  const { t } = useTranslation();
  const { formatCurrency, formatDate, formatTime } = useFormatters();
  const [expanded, setExpanded] = useState(false);

  const statusKey = order.status?.toLowerCase();
  const statusConfig = STATUS_CONFIGS[statusKey as OrderStatus] ?? UNKNOWN_STATUS_CONFIG;
  // Status labels are keyed by the backend status code; an unknown status
  // falls back to displaying the raw code
  const statusLabel = translateDynamic(`orders.status.${statusKey}`, {
    defaultValue: order.status,
  });
  const orderDate = new Date(order.created_at || order.order_date);
  const formattedDate = formatDate(orderDate);
  const formattedTime = formatTime(orderDate);

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
            {t('orders.itemsSummary', { count: order.item_count, total: order.total_quantity })}
          </Typography>
          <Typography variant="h6" color="primary" fontWeight={600}>
            {formatCurrency(order.total_price)}
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

        {/* Expanded Details: loaded the first time the card is opened */}
        <Collapse in={expanded} mountOnEnter>
          <Divider sx={{ my: 2 }} />
          <OrderCardDetails orderId={order.id} />
        </Collapse>
      </CardContent>
    </Card>
  );
};

export default OrderCard;
