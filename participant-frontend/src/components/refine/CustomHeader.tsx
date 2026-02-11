/**
 * Custom Header Component for Refine
 * App header with branding and user actions
 */
import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Badge,
  Box,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  useMediaQuery,
  useTheme,
  Skeleton,
} from '@mui/material';
import {
  ShoppingCart as ShoppingCartIcon,
  Menu as MenuIcon,
  Logout as LogoutIcon,
  AccountCircle as AccountIcon,
} from '@mui/icons-material';
import { useLogout, useGetIdentity, useNavigation } from '@refinedev/core';
import { useQuery } from '@tanstack/react-query';
import { useCartContext } from '../../providers/CartProvider';
import { CartDrawer } from '../../features/cart';
import { getThemeConfig } from '../../shared/api/endpoints';
import type { User } from '../../shared/types/api';

export const CustomHeader: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { go } = useNavigation();
  const { mutate: logout } = useLogout();
  const { data: user } = useGetIdentity<User>();
  const { totalItems } = useCartContext();

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [cartDrawerOpen, setCartDrawerOpen] = useState(false);

  // Fetch theme/branding
  const { data: themeConfig } = useQuery({
    queryKey: ['theme-config'],
    queryFn: getThemeConfig,
    staleTime: 5 * 60 * 1000,
  });

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    handleMenuClose();
    logout();
  };

  const handleAccount = () => {
    handleMenuClose();
    go({ to: '/account' });
  };

  return (
    <>
      <AppBar 
        position="fixed" 
        color="primary" 
        elevation={1}
        sx={{ 
          zIndex: (theme) => theme.zIndex.drawer + 1,
          left: { xs: 0, md: 260 }, // Leave space for sidebar on desktop
          width: { xs: '100%', md: 'calc(100% - 260px)' },
        }}
      >
        <Toolbar>
          {/* Logo / App Name */}
          <Box
            sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              cursor: 'pointer',
              mr: 2,
            }}
            onClick={() => go({ to: '/products' })}
          >
            {themeConfig?.logo ? (
              <Box
                component="img"
                src={themeConfig.logo}
                alt={themeConfig.app_name}
                sx={{ height: 40, mr: 1 }}
              />
            ) : null}
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                display: { xs: 'none', sm: 'block' },
              }}
            >
              {themeConfig?.app_name || 'Basketful'}
            </Typography>
          </Box>

          {/* Spacer */}
          <Box sx={{ flexGrow: 1 }} />

          {/* Desktop: Cart button */}
          {!isMobile && (
            <IconButton
              color="inherit"
              onClick={() => setCartDrawerOpen(true)}
              sx={{ mr: 1 }}
            >
              <Badge badgeContent={totalItems} color="secondary">
                <ShoppingCartIcon />
              </Badge>
            </IconButton>
          )}

          {/* User Menu */}
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            {user ? (
              <>
                <Typography
                  variant="body2"
                  sx={{
                    mr: 1,
                    display: { xs: 'none', md: 'block' },
                  }}
                >
                  {user.name || user.username}
                </Typography>
                <IconButton
                  onClick={handleMenuOpen}
                  color="inherit"
                  size="small"
                >
                  <Avatar sx={{ width: 32, height: 32, bgcolor: 'secondary.main' }}>
                    {(user.name || user.username).charAt(0).toUpperCase()}
                  </Avatar>
                </IconButton>
              </>
            ) : (
              <Skeleton variant="circular" width={32} height={32} />
            )}
          </Box>

          {/* User dropdown menu */}
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'right',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
          >
            {user && (
              <Box sx={{ px: 2, py: 1 }}>
                <Typography variant="subtitle2">{user.name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {user.customer_number}
                </Typography>
              </Box>
            )}
            <Divider />
            <MenuItem onClick={handleAccount}>
              <AccountIcon sx={{ mr: 1 }} fontSize="small" />
              My Account
            </MenuItem>
            <MenuItem onClick={handleLogout}>
              <LogoutIcon sx={{ mr: 1 }} fontSize="small" />
              Logout
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Cart Drawer */}
      <CartDrawer open={cartDrawerOpen} onClose={() => setCartDrawerOpen(false)} />
    </>
  );
};

export default CustomHeader;
