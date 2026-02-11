/**
 * App Header Component
 * Top bar with logo, desktop nav links, and user menu
 */
import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Menu,
  MenuItem,
  Box,
  Avatar,
  Divider,
  ListItemIcon,
  ListItemText,
  Button,
  Badge,
  Stack,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Logout,
  Person,
  Store,
  History,
  ShoppingCart,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../providers/AuthContext';
import { useThemeConfig } from '../shared/theme/dynamicTheme';
import { useCartContext } from '../providers/CartProvider';
import { CartDrawer } from '../features/cart/CartDrawer';

export const AppHeader: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { themeConfig } = useThemeConfig();
  const { totalItems } = useCartContext();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [cartOpen, setCartOpen] = useState(false);
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async () => {
    handleMenuClose();
    await logout();
    navigate('/login');
  };

  const handleAccount = () => {
    handleMenuClose();
    navigate('/account');
  };

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user) return '?';
    const first = user.first_name?.[0] || '';
    const last = user.last_name?.[0] || '';
    return (first + last).toUpperCase() || user.customer_number?.[0] || '?';
  };

  const isActive = (path: string) => location.pathname === path;

  // Desktop nav button style
  const navButtonSx = (path: string) => ({
    color: 'inherit',
    fontWeight: isActive(path) ? 600 : 400,
    borderBottom: isActive(path) ? 2 : 0,
    borderColor: 'white',
    borderRadius: 0,
    px: 2,
    py: 1,
    '&:hover': {
      bgcolor: 'rgba(255,255,255,0.1)',
    },
  });

  return (
    <>
      <AppBar position="sticky" elevation={1}>
        <Toolbar>
          {/* Logo/App Name */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
              mr: { xs: 'auto', md: 4 },
            }}
            onClick={() => navigate('/products')}
          >
            {themeConfig?.logo ? (
              <Box
                component="img"
                src={themeConfig.logo}
                alt={themeConfig.app_name || 'App'}
                sx={{ height: 32, maxWidth: 120, objectFit: 'contain' }}
              />
            ) : (
              <Typography variant="h6" component="div">
                {themeConfig?.app_name || 'Basketful'}
              </Typography>
            )}
          </Box>

          {/* Desktop Navigation Links - hidden on mobile */}
          <Stack
            direction="row"
            spacing={1}
            sx={{
              display: { xs: 'none', md: 'flex' },
              flexGrow: 1,
            }}
          >
            <Button
              startIcon={<Store />}
              onClick={() => navigate('/products')}
              sx={navButtonSx('/products')}
            >
              Shop
            </Button>
            <Button
              startIcon={<History />}
              onClick={() => navigate('/orders')}
              sx={navButtonSx('/orders')}
            >
              Orders
            </Button>
            <Button
              startIcon={<Person />}
              onClick={() => navigate('/account')}
              sx={navButtonSx('/account')}
            >
              Account
            </Button>
          </Stack>

          {/* Cart button - visible on desktop and tablets */}
          {isDesktop && (
            <IconButton
              color="inherit"
              onClick={() => setCartOpen(true)}
              sx={{ ml: 1 }}
            >
              <Badge badgeContent={totalItems} color="error" max={99}>
                <ShoppingCart />
              </Badge>
            </IconButton>
          )}

          {/* Cart button - visible on medium screens (tablets), hidden on mobile and large desktop */}
          <Box sx={{ display: { xs: 'none', md: 'flex', lg: 'none' }, mr: 2 }}>
            <IconButton color="inherit" onClick={() => setCartOpen(true)}>
              <Badge badgeContent={totalItems} color="error">
                <ShoppingCart />
              </Badge>
            </IconButton>
          </Box>

          {/* User Menu */}
          <IconButton
            color="inherit"
            onClick={handleMenuOpen}
            aria-label="User menu"
            aria-controls="user-menu"
            aria-haspopup="true"
          >
            <Avatar
              sx={{
                width: 36,
                height: 36,
                bgcolor: 'primary.dark',
                fontSize: '0.9rem',
              }}
            >
              {getUserInitials()}
            </Avatar>
          </IconButton>

          <Menu
            id="user-menu"
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            {/* User Info */}
            <Box sx={{ px: 2, py: 1 }}>
              <Typography variant="subtitle2">
                {user?.first_name} {user?.last_name}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {user?.customer_number}
              </Typography>
            </Box>

            <Divider />

            <MenuItem onClick={handleAccount}>
              <ListItemIcon>
                <Person fontSize="small" />
              </ListItemIcon>
              <ListItemText>My Account</ListItemText>
            </MenuItem>

            <Divider />

            <MenuItem onClick={handleLogout}>
              <ListItemIcon>
                <Logout fontSize="small" />
              </ListItemIcon>
              <ListItemText>Sign Out</ListItemText>
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Cart Drawer for tablet/medium screens */}
      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} />
    </>
  );
};

export default AppHeader;
