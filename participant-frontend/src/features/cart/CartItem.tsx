/**
 * Cart Item Component
 * Individual item in cart with quantity controls
 */
import React, { memo } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Avatar,
  Stack,
  Chip,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  Delete as DeleteIcon,
  ErrorOutline,
  WarningAmber,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { CartItemData } from '../../providers/CartProvider';
import { useCartContext } from '../../providers/CartProvider';
import { useValidation } from '../../providers/ValidationContext';
import { useFormatters } from '../../shared/hooks/useFormatters';
import { tokens } from '../../shared/theme/tokens';

interface CartItemProps {
  item: CartItemData;
}

const CartItemComponent: React.FC<CartItemProps> = ({ item }) => {
  const { t } = useTranslation();
  const { formatCurrency } = useFormatters();
  const { updateItemQuantity, removeItem } = useCartContext();
  const { getErrorsForProduct, getWarningsForProduct } = useValidation();

  const errors = getErrorsForProduct(item.productId);
  const warnings = getWarningsForProduct(item.productId);
  const hasError = errors.length > 0;
  const hasWarning = warnings.length > 0;

  const handleIncrease = () => {
    updateItemQuantity(item.id, (item.quantity || 1) + 1);
  };

  const handleDecrease = () => {
    updateItemQuantity(item.id, (item.quantity || 1) - 1);
  };

  const handleRemove = () => {
    removeItem(item.id);
  };

  const itemTotal = (item.price || 0) * (item.quantity || 1);

  return (
    <Box
      sx={{
        py: 1.5,
        px: 2,
        borderBottom: `1px solid ${tokens.border.default}`,
        bgcolor: hasError ? 'error.light' : hasWarning ? 'warning.light' : 'transparent',
        '&:last-child': {
          borderBottom: 0,
        },
      }}
    >
      <Stack direction="row" spacing={2} alignItems="flex-start">
        {/* Product Image */}
        <Avatar
          variant="rounded"
          src={item.image?.replace(/^http:/, 'https:')}
          alt={item.name}
          sx={{ width: 60, height: 60 }}
        >
          {item.name.charAt(0)}
        </Avatar>

        {/* Product Details */}
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 500,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {item.name}
          </Typography>

          {item.category && (
            <Typography variant="caption" color="text.secondary">
              {item.category}
            </Typography>
          )}

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
            <Typography variant="body2" color="text.secondary">
              {t('cart.priceTimesQuantity', {
                price: formatCurrency(item.price || 0),
                quantity: item.quantity || 1,
              })}
            </Typography>
            <Typography variant="body1" fontWeight={600} sx={{ color: tokens.brand.greenPrimary }}>
              {formatCurrency(itemTotal)}
            </Typography>
          </Box>

          {/* Error/Warning Messages */}
          {(hasError || hasWarning) && (
            <Stack direction="row" spacing={0.5} sx={{ mt: 1, flexWrap: 'wrap', gap: 0.5 }}>
              {errors.map((error, idx) => (
                <Chip
                  key={`error-${idx}`}
                  icon={<ErrorOutline />}
                  label={error.message}
                  color="error"
                  size="small"
                  sx={{ height: 'auto', py: 0.5, '& .MuiChip-label': { whiteSpace: 'normal' } }}
                />
              ))}
              {warnings.map((warning, idx) => (
                <Chip
                  key={`warning-${idx}`}
                  icon={<WarningAmber />}
                  label={warning.message}
                  color="warning"
                  size="small"
                  sx={{ height: 'auto', py: 0.5, '& .MuiChip-label': { whiteSpace: 'normal' } }}
                />
              ))}
            </Stack>
          )}
        </Box>

        {/* Quantity Controls */}
        <Stack direction="column" alignItems="center" spacing={0.5}>
          <Stack direction="row" alignItems="center" spacing={0}>
            <IconButton
              size="small"
              onClick={handleDecrease}
              aria-label={t('cart.decreaseQuantity')}
            >
              <RemoveIcon fontSize="small" />
            </IconButton>
            <Typography
              variant="body1"
              sx={{
                minWidth: 28,
                textAlign: 'center',
                fontWeight: 600,
              }}
            >
              {item.quantity || 1}
            </Typography>
            <IconButton
              size="small"
              onClick={handleIncrease}
              aria-label={t('cart.increaseQuantity')}
              disabled={!item.available}
            >
              <AddIcon fontSize="small" />
            </IconButton>
          </Stack>

          <IconButton
            size="small"
            onClick={handleRemove}
            color="error"
            aria-label={t('cart.removeFromCart')}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Stack>
      </Stack>
    </Box>
  );
};

export const CartItem = memo(CartItemComponent);
