/**
 * Custom Sider Component for Refine
 * Collapsible left navigation with categories.
 * The cart lives in DesktopCartPanel (right side) — not here.
 */
import React, { useState } from 'react';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Divider,
  Skeleton,
  Tooltip,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Category as CategoryIcon,
  Receipt as ReceiptIcon,
  AccountCircle as AccountIcon,
  Storefront as StorefrontIcon,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
} from '@mui/icons-material';
import { useGo, useResourceParams } from '@refinedev/core';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { getCategories, getProducts } from '../../shared/api/endpoints';
import { useCartValidation } from '../../shared/hooks/useCartValidation';

const SIDER_WIDTH = 240;
const SIDER_COLLAPSED_WIDTH = 64;

export const CustomSider: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const go = useGo();
  const { resource } = useResourceParams();
  const { remainingBudget, isOverBudget } = useCartValidation();
  const [searchParams] = useSearchParams();
  const selectedCategory = searchParams.get('category');
  const [collapsed, setCollapsed] = useState(false);

  const siderWidth = collapsed ? SIDER_COLLAPSED_WIDTH : SIDER_WIDTH;

  // Fetch categories for the sidebar
  const { data: categories = [], isLoading: categoriesLoading } = useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
    staleTime: 5 * 60 * 1000,
  });
  
  // Fetch products to calculate counts per category
  const { data: products = [] } = useQuery({
    queryKey: ['products'],
    queryFn: () => getProducts(),
    staleTime: 60 * 1000,
  });
  
  // Calculate product counts per category
  const productCounts = React.useMemo(() => {
    const counts: Record<number, number> = {};
    products.forEach(product => {
      if (product.category) {
        counts[product.category] = (counts[product.category] || 0) + 1;
      }
    });
    return counts;
  }, [products]);

  const menuItems = [
    { key: 'products', label: 'Shop', icon: <StorefrontIcon />, path: '/products' },
    { key: 'orders', label: 'Order History', icon: <ReceiptIcon />, path: '/orders' },
    { key: 'account', label: 'My Account', icon: <AccountIcon />, path: '/account' },
  ];

  // Don't render sider on mobile - use bottom nav instead
  if (isMobile) {
    return null;
  }

  return (
    <>
      {/* Spacer to push content right — width animates with sidebar */}
      <Box
        sx={{
          width: siderWidth,
          flexShrink: 0,
          transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
          display: { xs: 'none', md: 'block' },
        }}
      />

      {/* Fixed Drawer */}
      <Box
        component="nav"
        sx={{
          position: 'fixed',
          top: 64, // sits below AppBar, which is 64px tall
          zIndex: (theme) => theme.zIndex.appBar - 1,
          width: siderWidth,
          display: { xs: 'none', md: 'flex' },
          transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        }}
      >
        <Drawer
          variant="permanent"
          sx={{
            width: siderWidth,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: siderWidth,
              boxSizing: 'border-box',
              top: 64,
              height: 'calc(100vh - 64px)',
              borderRight: 1,
              borderColor: 'divider',
              overflowX: 'hidden',
              transition: theme.transitions.create('width', {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
            },
          }}
          open
        >
          {/* Budget Banner + collapse toggle */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              px: collapsed ? 1 : 2,
              py: 1.5,
              bgcolor: isOverBudget ? 'error.dark' : 'primary.dark',
              color: 'primary.contrastText',
              flexShrink: 0,
            }}
          >
            {!collapsed && (
              <Typography variant="body2" sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
                Available: ${Number(remainingBudget ?? 0).toFixed(2)}
              </Typography>
            )}
            <Tooltip title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} placement="right">
              <IconButton
                size="small"
                onClick={() => setCollapsed(c => !c)}
                sx={{ color: 'inherit', ml: collapsed ? 'auto' : 0 }}
              >
                {collapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
              </IconButton>
            </Tooltip>
          </Box>

          {/* Navigation */}
          <List sx={{ pt: 1 }}>
            {menuItems.map((item) => {
              const isSelected = resource?.name === item.key;
              return (
                <ListItem key={item.key} disablePadding>
                  <Tooltip title={collapsed ? item.label : ''} placement="right">
                    <ListItemButton
                      selected={isSelected}
                      onClick={() => go({ to: item.path })}
                      sx={{
                        minHeight: 48,
                        justifyContent: collapsed ? 'center' : 'initial',
                        px: collapsed ? 1.5 : 2,
                        '&.Mui-selected': {
                          bgcolor: 'primary.main',
                          color: 'primary.contrastText',
                          '& .MuiListItemIcon-root': { color: 'primary.contrastText' },
                          '&:hover': { bgcolor: 'primary.dark' },
                        },
                      }}
                    >
                      <ListItemIcon
                        sx={{
                          minWidth: 0,
                          mr: collapsed ? 0 : 2,
                          color: isSelected ? 'primary.contrastText' : 'inherit',
                          justifyContent: 'center',
                        }}
                      >
                        {item.icon}
                      </ListItemIcon>
                      {!collapsed && <ListItemText primary={item.label} />}
                    </ListItemButton>
                  </Tooltip>
                </ListItem>
              );
            })}
          </List>

          {!collapsed && (
            <>
              <Divider />

              {/* Categories Section */}
              <Box sx={{ px: 2, pt: 1.5, pb: 0.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                <CategoryIcon color="primary" fontSize="small" />
                <Typography variant="subtitle2" color="primary" fontWeight={600} sx={{ letterSpacing: '0.05em' }}>
                  CATEGORIES
                </Typography>
              </Box>

              <Box sx={{ overflow: 'auto', flex: 1 }}>
                <List component="div" disablePadding>
                  {categoriesLoading ? (
                    Array.from({ length: 5 }).map((_, index) => (
                      <ListItem key={index} sx={{ pl: 3 }}>
                        <Skeleton width="100%" />
                      </ListItem>
                    ))
                  ) : (
                    <>
                      <ListItemButton
                        sx={{ pl: 3 }}
                        selected={resource?.name === 'products' && !selectedCategory}
                        onClick={() => go({ to: '/products' })}
                      >
                        <ListItemText
                          primary="All Products"
                          secondary={`${products.length} items`}
                        />
                      </ListItemButton>
                      {categories.map((category) => (
                        <ListItemButton
                          key={category.id}
                          sx={{ pl: 3 }}
                          selected={selectedCategory === String(category.id)}
                          onClick={() => go({ to: '/products', query: { category: String(category.id) } })}
                        >
                          <ListItemText
                            primary={category.name}
                            secondary={`${productCounts[category.id] ?? 0} items`}
                          />
                        </ListItemButton>
                      ))}
                    </>
                  )}
                </List>
              </Box>
            </>
          )}
        </Drawer>
      </Box>
    </>
  );
};

export default CustomSider;
