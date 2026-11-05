/**
 * Phone-only cart bar pinned to the bottom of the screen.
 *
 * On phones the sider (with the balance banner) is hidden, so this bar is
 * where a participant sees what's left in each balance and gets to the cart.
 * Keep it in AppLayout's mobile branch — AppLayout.test.tsx fails if it
 * disappears (it did once, silently, in the Refine migration).
 */
import React from 'react';
import { Badge, Box, Button, Paper, Typography } from '@mui/material';
import { ShoppingCart as ShoppingCartIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useCartContext } from '../../providers/CartProvider';
import { useFormatters } from '../../shared/hooks/useFormatters';
import { BudgetSummary } from '../BudgetSummary';

/** Height the page content must leave free at the bottom on phones. */
export const MOBILE_CART_BAR_HEIGHT = 72;

interface MobileCartBarProps {
  onOpenCart: () => void;
}

export const MobileCartBar: React.FC<MobileCartBarProps> = ({ onOpenCart }) => {
  const { t } = useTranslation();
  const { formatCurrency } = useFormatters();
  const { totalItems, cartTotal } = useCartContext();

  return (
    <Paper
      component="section"
      role="region"
      aria-label={t('cart.summaryLabel')}
      data-testid="mobile-cart-bar"
      elevation={8}
      square
      sx={{
        position: 'fixed',
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: (theme) => theme.zIndex.appBar,
        minHeight: MOBILE_CART_BAR_HEIGHT,
        px: 2,
        pt: 1,
        // Clear the iPhone home indicator
        pb: 'calc(8px + env(safe-area-inset-bottom))',
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        bgcolor: 'primary.dark',
        color: 'primary.contrastText',
      }}
    >
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          {t('cart.title', { count: totalItems })} · {formatCurrency(cartTotal)}
        </Typography>
        <BudgetSummary variant="inline" color="primary.contrastText" />
      </Box>
      <Button
        variant="contained"
        color="secondary"
        onClick={onOpenCart}
        startIcon={
          <Badge badgeContent={totalItems} color="error">
            <ShoppingCartIcon />
          </Badge>
        }
        sx={{ flexShrink: 0, whiteSpace: 'nowrap' }}
      >
        {t('cart.viewCart')}
      </Button>
    </Paper>
  );
};
