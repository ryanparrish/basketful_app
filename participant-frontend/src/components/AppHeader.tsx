/**
 * App Header Component
 * Top bar with logo and user menu
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
} from '@mui/material';
import {
  Menu as MenuIcon,
  Logout,
  Person,
  Settings,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../providers/AuthContext';
import { useThemeConfig } from '../shared/theme/dynamicTheme';

export const AppHeader: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { themeConfig } = useThemeConfig();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

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

  return (
    <AppBar position="sticky" elevation={1}>
      <Toolbar>
        {/* Logo/App Name */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            flexGrow: 1,
            cursor: 'pointer',
          }}
          onClick={() => navigate('/products')}
        >
          {themeConfig?.logo ? (
            <Box
              component="img"
              src={themeConfig.logo}
              alt={themeConfig.app_name || 'App'}
              sx={{
                height: 32,
                maxWidth: 120,
                objectFit: 'contain',
              }}
            />
          ) : (
            <Typography variant="h6" component="div">
              {themeConfig?.app_name || 'Basketful'}
            </Typography>
          )}
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
              width: 32,
              height: 32,
              bgcolor: 'secondary.main',
              fontSize: '0.875rem',
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
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
          }}
          transformOrigin={{
            vertical: 'top',
            horizontal: 'right',
          }}
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
  );
};

export default AppHeader;
