/**
 * Desktop Cart Panel
 * Persistent right sidebar cart for desktop view
 */
import React from 'react';
import {
  Box,
  Typography,
  Button,
  Divider,
  Stack,
  IconButton,
  Paper,
} from '@mui/material';
import {
  ShoppingCart as CartIcon,
  DeleteSweep as ClearIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useCartContext } from '../providers/CartProvider';
import { useCanCheckout } from '../providers/ValidationContext';
import { CartItem } from '../features/cart/CartItem';
import { ValidationFeedback } from '../features/cart/ValidationFeedback';
import type { CartItemData } from '../providers/CartProvider';
import { DESKTOP_CART_WIDTH } from '../shared/constants/layout';

export const DesktopCartPanel: React.FC = () => {
  const navigate = useNavigate();
  const { items, totalItems, cartTotal, isEmpty, clearCart } = useCartContext();
  const { canCheckout, checkoutBlockedReason, balances } = useCanCheckout();

  const handleCheckout = () => {
    navigate('/checkout');
  };

  const handleClearCart = () => {
    if (window.confirm('Are you sure you want to clear your cart?')) {
      clearCart();
    }
  };

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'fixed',
        top: 64, // Below AppBar
        right: 0,
        width: DESKTOP_CART_WIDTH,
        height: 'calc(100vh - 64px)',
        borderLeft: 1,
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.paper',
        zIndex: 100,
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Stack direction="row" alignItems="center" spacing={1}>
          <CartIcon color="primary" />
          <Typography variant="h6">Cart ({totalItems})</Typography>
        </Stack>
        {!isEmpty && (
          <IconButton
            onClick={handleClearCart}
            size="small"
            color="error"
            aria-label="Clear cart"
          >
            <ClearIcon />
          </IconButton>
        )}
      </Box>

      {/* Cart Content */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        {isEmpty ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              p: 3,
            }}
          >
            <CartIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
            <Typography variant="body1" color="text.secondary" align="center">
              Your cart is empty
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
              Add items from the product list
            </Typography>
          </Box>
        ) : (
          <>
            {/* Validation Feedback */}
            <Box sx={{ px: 2, pt: 2 }}>
              <ValidationFeedback compact />
            </Box>

            {/* Cart Items */}
            <Box sx={{ px: 1 }}>
              {items.map((item: CartItemData) => (
                <CartItem key={item.id} item={item} />
              ))}
            </Box>
          </>
        )}
      </Box>

      {/* Footer with Totals */}
      {!isEmpty && (
        <Box sx={{ borderTop: 1, borderColor: 'divider', p: 2 }}>
          {balances && (
            <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Budget Remaining:
              </Typography>
              <Typography variant="body2" fontWeight={500}>
                ${balances.remaining_budget.toFixed(2)}
              </Typography>
            </Stack>
          )}

          <Divider sx={{ my: 1 }} />

          <Stack direction="row" justifyContent="space-between" sx={{ mb: 2 }}>
            <Typography variant="h6">Total:</Typography>
            <Typography variant="h6" color="primary" fontWeight={600}>
              ${cartTotal.toFixed(2)}
            </Typography>
          </Stack>

          <Button
            fullWidth
            variant="contained"
            size="large"
            onClick={handleCheckout}
            disabled={!canCheckout}
          >
            {canCheckout ? 'Checkout' : checkoutBlockedReason || 'Cannot Checkout'}
          </Button>
        </Box>
      )}
    </Paper>
  );
};

export default DesktopCartPanel;
