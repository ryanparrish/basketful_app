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
import type { Product } from '../../shared/types/api';
import { useCartContext, useItemInCart } from '../../providers/CartProvider';
import { useValidation } from '../../providers/ValidationContext';

interface ProductCardProps {
  product: Product;
}

const ProductCardComponent: React.FC<ProductCardProps> = ({ product }) => {
  const { addItem, updateItemQuantity, removeItem } = useCartContext();
  const { isInCart, quantity } = useItemInCart(product.id);
  const { getErrorsForProduct, getWarningsForProduct } = useValidation();

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
  };

  const handleRemove = () => {
    if (quantity <= 1) {
      removeItem(`product-${product.id}`);
    } else {
      updateItemQuantity(`product-${product.id}`, quantity - 1);
    }
  };

  const isUnavailable = !product.is_available;
  const displayPrice = product.price ? `$${product.price.toFixed(2)}` : 'Free';
  const unitLabel = product.unit || 'each';

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
          <Tooltip title={errors[0]?.message || 'Error'}>
            <Chip
              icon={<ErrorOutline />}
              label="Error"
              color="error"
              size="small"
            />
          </Tooltip>
        )}
        {hasWarning && !hasError && (
          <Tooltip title={warnings[0]?.message || 'Warning'}>
            <Chip
              icon={<WarningAmber />}
              label="Warning"
              color="warning"
              size="small"
            />
          </Tooltip>
        )}
        {isUnavailable && (
          <Chip label="Unavailable" size="small" />
        )}
      </Box>

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
          backgroundImage: product.image ? `url(${product.image})` : 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {!product.image && (
          <Typography variant="body2" color="text.secondary">
            No image
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
              aria-label="Remove one"
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
              aria-label="Add one"
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
            aria-label="Add to cart"
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
