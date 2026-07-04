/**
 * Product Card Component
 * Displays product with add-to-cart functionality and validation feedback
 */
import React, { memo } from 'react';
import {
  Card,
  CardContent,
  CardMedia,
  CardActions,
  Typography,
  Box,
  IconButton,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  ErrorOutline,
  WarningAmber,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { Product } from '../../shared/types/api';
import { useCartContext, useItemInCart } from '../../providers/CartProvider';
import { useValidation } from '../../providers/ValidationContext';
import { useFormatters } from '../../shared/hooks/useFormatters';

interface ProductCardProps {
  product: Product;
}

const ProductCardComponent: React.FC<ProductCardProps> = ({ product }) => {
  const { t } = useTranslation();
  const { formatCurrency } = useFormatters();
  const { addItem, updateItemQuantity, removeItem } = useCartContext();
  const { isInCart, quantity } = useItemInCart(product.id);
  const { getErrorsForProduct, getWarningsForProduct } = useValidation();
  const [showAddAnimation, setShowAddAnimation] = React.useState(false);

  const errors = getErrorsForProduct(product.id);
  const warnings = getWarningsForProduct(product.id);
  const hasError = errors.length > 0;
  const hasWarning = warnings.length > 0;

  const handleAdd = () => {
    if (isInCart) {
      updateItemQuantity(`product-${product.id}`, quantity + 1);
    } else {
      addItem(product, 1);
    }
    // Trigger animation
    setShowAddAnimation(true);
    setTimeout(() => setShowAddAnimation(false), 1000);
  };

  const handleRemove = () => {
    if (quantity <= 1) {
      removeItem(`product-${product.id}`);
    } else {
      updateItemQuantity(`product-${product.id}`, quantity - 1);
    }
  };

  const isUnavailable = !product.is_available;
  const displayPrice = product.price ? formatCurrency(product.price) : t('common.free');
  const unitLabel = product.unit || t('common.each');

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        opacity: isUnavailable ? 0.6 : 1,
        border: hasError ? 2 : hasWarning ? 1 : 0,
        borderColor: hasError ? 'error.main' : hasWarning ? 'warning.main' : 'transparent',
      }}
    >
      {/* Status Badges */}
      <Box sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1, display: 'flex', gap: 0.5 }}>
        {hasError && (
          <Tooltip title={errors[0]?.message || t('common.error')}>
            <Chip
              icon={<ErrorOutline />}
              label={t('common.error')}
              color="error"
              size="small"
            />
          </Tooltip>
        )}
        {hasWarning && !hasError && (
          <Tooltip title={warnings[0]?.message || t('common.warning')}>
            <Chip
              icon={<WarningAmber />}
              label={t('common.warning')}
              color="warning"
              size="small"
            />
          </Tooltip>
        )}
        {isUnavailable && (
          <Chip label={t('common.unavailable')} size="small" />
        )}
      </Box>

      {/* Quick Add Button - Top Left */}
      {!isInCart && !isUnavailable && (
        <Box sx={{ position: 'absolute', top: 8, left: 8, zIndex: 1 }}>
          <IconButton
            size="small"
            onClick={handleAdd}
            sx={{
              bgcolor: 'primary.main',
              color: 'white',
              '&:hover': {
                bgcolor: 'primary.dark',
              },
              boxShadow: 2,
            }}
          >
            <AddIcon fontSize="small" />
          </IconButton>
        </Box>
      )}

      {/* Add to Cart Animation */}
      {showAddAnimation && (
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 10,
            pointerEvents: 'none',
            animation: 'fadeOutUp 1s ease-out',
            '@keyframes fadeOutUp': {
              '0%': {
                opacity: 1,
                transform: 'translate(-50%, -50%) scale(1)',
              },
              '100%': {
                opacity: 0,
                transform: 'translate(-50%, -100%) scale(1.5)',
              },
            },
          }}
        >
          <Typography variant="h4" color="success.main" sx={{ fontWeight: 'bold' }}>
            +1
          </Typography>
        </Box>
      )}

      {/* Quantity Badge */}
      {isInCart && (
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            left: 8,
            zIndex: 1,
          }}
        >
          <Chip
            label={quantity}
            color="primary"
            size="small"
            sx={{ fontWeight: 'bold' }}
          />
        </Box>
      )}

      {/* Product Image */}
      <CardMedia
        component="div"
        sx={{
          height: 140,
          backgroundColor: 'grey.200',
          backgroundSize: 'contain',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          backgroundImage: product.image ? `url(${product.image.replace(/^http:/, 'https:')})` : 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {!product.image && (
          <Typography variant="body2" color="text.secondary">
            {t('common.noImage')}
          </Typography>
        )}
      </CardMedia>

      {/* Product Info */}
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        <Typography
          variant="subtitle1"
          component="h3"
          sx={{
            fontWeight: 500,
            lineHeight: 1.3,
            mb: 0.5,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {product.name}
        </Typography>

        {product.category_name && (
          <Typography variant="caption" color="text.secondary" display="block">
            {product.category_name}
          </Typography>
        )}

        <Box sx={{ display: 'flex', alignItems: 'baseline', mt: 1 }}>
          <Typography variant="h6" color="primary" sx={{ fontWeight: 600 }}>
            {displayPrice}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>
            / {unitLabel}
          </Typography>
        </Box>
      </CardContent>

      {/* Add to Cart Actions */}
      <CardActions sx={{ justifyContent: 'center', pb: 2 }}>
        {isInCart ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton
              size="small"
              onClick={handleRemove}
              color="primary"
              aria-label={t('products.removeOne')}
              sx={{
                border: 1,
                borderColor: 'primary.main',
              }}
            >
              <RemoveIcon />
            </IconButton>
            <Typography
              variant="h6"
              sx={{ minWidth: 32, textAlign: 'center' }}
            >
              {quantity}
            </Typography>
            <IconButton
              size="small"
              onClick={handleAdd}
              color="primary"
              disabled={isUnavailable}
              aria-label={t('products.addOne')}
              sx={{
                border: 1,
                borderColor: 'primary.main',
              }}
            >
              <AddIcon />
            </IconButton>
          </Box>
        ) : (
          <IconButton
            onClick={handleAdd}
            color="primary"
            disabled={isUnavailable}
            aria-label={t('products.addToCart')}
            sx={{
              border: 2,
              borderColor: 'primary.main',
              '&:hover': {
                backgroundColor: 'primary.main',
                color: 'primary.contrastText',
              },
            }}
          >
            <AddIcon />
          </IconButton>
        )}
      </CardActions>

      {/* Error Message */}
      {hasError && (
        <Box sx={{ px: 2, pb: 1 }}>
          <Typography variant="caption" color="error">
            {errors[0]?.message}
          </Typography>
        </Box>
      )}
    </Card>
  );
};

export const ProductCard = memo(ProductCardComponent);
