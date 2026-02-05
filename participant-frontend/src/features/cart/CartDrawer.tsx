/**
 * Cart Drawer Component
 * Slide-out cart panel with items and checkout button
 */
import React from 'react';
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Button,
  Divider,
  Stack,
} from '@mui/material';
import {
  Close as CloseIcon,
  ShoppingCart as CartIcon,
  DeleteSweep as ClearIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useCartContext } from '../../providers/CartProvider';
import { useCanCheckout } from '../../providers/ValidationContext';
import { CartItem } from './CartItem';
import { ValidationFeedback } from './ValidationFeedback';
import type { CartItemData } from '../../providers/CartProvider';

interface CartDrawerProps {
  open: boolean;
  onClose: () => void;
}

export const CartDrawer: React.FC<CartDrawerProps> = ({ open, onClose }) => {
  const navigate = useNavigate();
  const { items, totalItems, cartTotal, isEmpty, clearCart } = useCartContext();
  const { canCheckout, checkoutBlockedReason, balances } = useCanCheckout();

  const handleCheckout = () => {
    onClose();
    navigate('/checkout');
  };

  const handleClearCart = () => {
    if (window.confirm('Are you sure you want to clear your cart?')) {
      clearCart();
    }
  };

  const handleContinueShopping = () => {
    onClose();
    navigate('/products');
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: '100%', sm: 400 },
          maxWidth: '100%',
        },
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
          <Typography variant="h6">
            Cart ({totalItems})
          </Typography>
        </Stack>
        <Stack direction="row" spacing={1}>
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
          <IconButton onClick={onClose} aria-label="Close cart">
            <CloseIcon />
          </IconButton>
        </Stack>
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
              p: 4,
            }}
          >
            <CartIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              Your cart is empty
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 3 }}>
              Start adding products to your cart
            </Typography>
            <Button variant="contained" onClick={handleContinueShopping}>
              Browse Products
            </Button>
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
          {/* Budget Info */}
          {balances && (
            <Box sx={{ mb: 2 }}>
              <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
                <Typography variant="body2" color="text.secondary">
                  Budget Remaining:
                </Typography>
                <Typography variant="body2" fontWeight={500}>
                  ${balances.remaining_budget.toFixed(2)}
                </Typography>
              </Stack>
            </Box>
          )}

          <Divider sx={{ my: 1 }} />

          {/* Cart Total */}
          <Stack direction="row" justifyContent="space-between" sx={{ mb: 2 }}>
            <Typography variant="h6">Total:</Typography>
            <Typography variant="h6" color="primary" fontWeight={600}>
              ${cartTotal.toFixed(2)}
            </Typography>
          </Stack>

          {/* Checkout Button */}
          <Button
            fullWidth
            variant="contained"
            size="large"
            onClick={handleCheckout}
            disabled={!canCheckout}
            sx={{ py: 1.5 }}
          >
            {canCheckout ? 'Proceed to Checkout' : checkoutBlockedReason || 'Cannot Checkout'}
          </Button>

          {/* Continue Shopping */}
          <Button
            fullWidth
            variant="text"
            onClick={handleContinueShopping}
            sx={{ mt: 1 }}
          >
            Continue Shopping
          </Button>
        </Box>
      )}
    </Drawer>
  );
};

export default CartDrawer;
