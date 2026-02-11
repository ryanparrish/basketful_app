/**
 * Bottom Navigation Component
 * Mobile navigation bar with cart badge
 */
import React, { useState } from 'react';
import {
  Paper,
  BottomNavigation as MuiBottomNavigation,
  BottomNavigationAction,
  Badge,
  Fab,
  Box,
} from '@mui/material';
import {
  Store,
  ShoppingCart,
  History,
  Person,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useCartContext } from '../providers/CartProvider';
import { CartDrawer } from '../features/cart/CartDrawer';

export const BottomNavigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { totalItems } = useCartContext();
  const [cartOpen, setCartOpen] = useState(false);

  // Map paths to navigation values
  const getNavValue = () => {
    const path = location.pathname;
    if (path.startsWith('/products')) return 'products';
    if (path.startsWith('/orders')) return 'orders';
    if (path.startsWith('/account')) return 'account';
    return 'products';
  };

  const handleNavChange = (_event: React.SyntheticEvent, newValue: string) => {
    if (newValue === 'cart') {
      setCartOpen(true);
      return;
    }
    
    switch (newValue) {
      case 'products':
        navigate('/products');
        break;
      case 'orders':
        navigate('/orders');
        break;
      case 'account':
        navigate('/account');
        break;
    }
  };

  const handleCartClick = () => {
    setCartOpen(true);
  };

  return (
    <>
      {/* Cart FAB */}
      <Box
        sx={{
          position: 'fixed',
          bottom: { xs: 70, lg: 16 },
          right: 16,
          zIndex: 1000,
        }}
      >
        <Fab
          color="primary"
          aria-label="Open cart"
          onClick={handleCartClick}
          sx={{
            boxShadow: 4,
          }}
        >
          <Badge
            badgeContent={totalItems}
            color="error"
            max={99}
          >
            <ShoppingCart />
          </Badge>
        </Fab>
      </Box>

      {/* Bottom Navigation */}
      <Paper
        sx={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 1100,
        }}
        elevation={8}
      >
        <MuiBottomNavigation
          value={getNavValue()}
          onChange={handleNavChange}
          showLabels
          sx={{
            height: 64,
            '& .MuiBottomNavigationAction-root': {
              minWidth: 0,
              padding: '6px 12px',
            },
          }}
        >
          <BottomNavigationAction
            label="Shop"
            value="products"
            icon={<Store />}
          />
          <BottomNavigationAction
            label="Orders"
            value="orders"
            icon={<History />}
          />
          <BottomNavigationAction
            label="Account"
            value="account"
            icon={<Person />}
          />
        </MuiBottomNavigation>
      </Paper>

      {/* Cart Drawer */}
      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} />
    </>
  );
};

export default BottomNavigation;
