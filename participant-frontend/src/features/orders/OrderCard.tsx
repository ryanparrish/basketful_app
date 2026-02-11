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
import type { Order, OrderListItem } from '../../shared/types/api';

interface OrderCardProps {
  order: Order | OrderListItem;
}

const getStatusConfig = (status: string) => {
  const configs: Record<string, { color: 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'; icon: React.ReactNode; label: string }> = {
    pending: { color: 'warning', icon: <Pending />, label: 'Pending' },
    confirmed: { color: 'info', icon: <Schedule />, label: 'Confirmed' },
    processing: { color: 'primary', icon: <Schedule />, label: 'Processing' },
    shipped: { color: 'secondary', icon: <LocalShipping />, label: 'Shipped' },
    delivered: { color: 'success', icon: <CheckCircle />, label: 'Delivered' },
    completed: { color: 'success', icon: <CheckCircle />, label: 'Completed' },
    cancelled: { color: 'error', icon: <Cancel />, label: 'Cancelled' },
  };
  return configs[status?.toLowerCase()] || { color: 'default', icon: <Pending />, label: status };
};

export const OrderCard: React.FC<OrderCardProps> = ({ order }) => {
  const [expanded, setExpanded] = useState(false);

  const statusConfig = getStatusConfig(order.status);
  const orderDate = new Date(order.created_at || order.order_date);
  const formattedDate = orderDate.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
  const formattedTime = orderDate.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });

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
              Order #{order.id}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formattedDate} at {formattedTime}
            </Typography>
          </Box>
          <Chip
            icon={statusConfig.icon as React.ReactElement}
            label={statusConfig.label}
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
            {itemCount} {itemCount === 1 ? 'item' : 'items'} ({totalQuantity} total)
          </Typography>
          <Typography variant="h6" color="primary" fontWeight={600}>
            ${(order.total || order.total_price).toFixed(2)}
          </Typography>
        </Stack>

        {/* Expand Button */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
          <IconButton
            onClick={() => setExpanded(!expanded)}
            size="small"
            aria-expanded={expanded}
            aria-label={expanded ? 'Show less' : 'Show details'}
          >
            {expanded ? <ExpandLess /> : <ExpandMore />}
          </IconButton>
        </Box>

        {/* Expanded Details */}
        <Collapse in={expanded}>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" gutterBottom>
            Items
          </Typography>
          <List disablePadding dense>
            {order.items?.map((item, idx) => (
              <ListItem key={idx} disableGutters>
                <ListItemText
                  primary={item.product_name || `Product #${item.product_id || item.product}`}
                  secondary={`Qty: ${item.quantity}`}
                />
                <Typography variant="body2">
                  ${(item.price * item.quantity).toFixed(2)}
                </Typography>
              </ListItem>
            ))}
          </List>

          {order.notes && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" gutterBottom>
                Notes
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
