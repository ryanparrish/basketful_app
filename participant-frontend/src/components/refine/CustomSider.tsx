/**
 * Custom Sider Component for Refine
 * Shows categories + cart summary on desktop
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
  Badge,
  Collapse,
  Skeleton,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  ShoppingCart as ShoppingCartIcon,
  ExpandLess,
  ExpandMore,
  Category as CategoryIcon,
  Home as HomeIcon,
  Receipt as ReceiptIcon,
  AccountCircle as AccountIcon,
  Storefront as StorefrontIcon,
} from '@mui/icons-material';
import { useGo, useResourceParams } from '@refinedev/core';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { useCartContext } from '../../providers/CartProvider';
import { getCategories, getProducts } from '../../shared/api/endpoints';
import { useCartValidation } from '../../shared/hooks/useCartValidation';
import { CartDrawer } from '../../features/cart';

const SIDER_WIDTH = 260;

interface CustomSiderProps {
  collapsed?: boolean;
}

export const CustomSider: React.FC<CustomSiderProps> = ({ collapsed = false }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const go = useGo();
  const { resource } = useResourceParams();
  const { totalItems, cartTotal } = useCartContext();
  const { remainingBudget, isOverBudget } = useCartValidation();
  const [searchParams] = useSearchParams();
  const selectedCategory = searchParams.get('category');
  
  const [categoriesOpen, setCategoriesOpen] = useState(true);
  const [cartDrawerOpen, setCartDrawerOpen] = useState(false);

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
      {/* Spacer to push content right */}
      <Box
        sx={{
          width: SIDER_WIDTH,
          flexShrink: 0,
          display: { xs: 'none', md: 'block' },
        }}
      />
      {/* Fixed Drawer */}
      <Box
        component="nav"
        sx={{
          position: 'fixed',
          zIndex: (theme) => theme.zIndex.drawer,
          width: SIDER_WIDTH,
          display: { xs: 'none', md: 'flex' },
        }}
      >
        <Drawer
          variant="permanent"
          sx={{
            width: SIDER_WIDTH,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: SIDER_WIDTH,
              boxSizing: 'border-box',
              top: 0,
              height: '100vh',
              borderRight: 1,
              borderColor: 'divider',
            },
          }}
          open
        >
          {/* Budget Banner at top of sidebar (matches header height) */}
          <Box
            sx={{
              height: 64,
              display: 'flex',
              alignItems: 'center',
              px: 2,
              bgcolor: isOverBudget ? 'error.light' : 'primary.main',
              color: isOverBudget ? 'error.contrastText' : 'primary.contrastText',
            }}
          >
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              Budget: ${remainingBudget?.toFixed(2) ?? '0.00'}
            </Typography>
          </Box>

          {/* Navigation */}
          <List>
          {menuItems.map((item) => (
            <ListItem key={item.key} disablePadding>
              <ListItemButton
                selected={resource?.name === item.key}
                onClick={() => go({ to: item.path })}
                sx={{
                  '&.Mui-selected': {
                    bgcolor: 'primary.light',
                    color: 'primary.main',
                    '&:hover': {
                      bgcolor: 'primary.light',
                    },
                  },
                }}
              >
                <ListItemIcon sx={{ color: 'inherit' }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>

        <Divider />

        {/* Categories Section */}
        <ListItem disablePadding>
          <ListItemButton onClick={() => setCategoriesOpen(!categoriesOpen)}>
            <ListItemIcon>
              <CategoryIcon />
            </ListItemIcon>
            <ListItemText primary="Categories" />
            {categoriesOpen ? <ExpandLess /> : <ExpandMore />}
          </ListItemButton>
        </ListItem>

        <Collapse in={categoriesOpen} timeout="auto" unmountOnExit>
          <List component="div" disablePadding>
            {categoriesLoading ? (
              // Skeleton loading state
              Array.from({ length: 5 }).map((_, index) => (
                <ListItem key={index} sx={{ pl: 4 }}>
                  <Skeleton width="100%" />
                </ListItem>
              ))
            ) : (
              <>
                {/* All Products option */}
                <ListItemButton
                  sx={{ pl: 4 }}
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
                    sx={{ pl: 4 }}
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
        </Collapse>

        {/* Cart Summary at bottom */}
        <Box sx={{ mt: 'auto', p: 2, borderTop: 1, borderColor: 'divider' }}>
          <ListItemButton
            onClick={() => setCartDrawerOpen(true)}
            sx={{
              borderRadius: 1,
              bgcolor: 'background.paper',
              border: 1,
              borderColor: 'divider',
            }}
          >
            <ListItemIcon>
              <Badge badgeContent={totalItems} color="primary">
                <ShoppingCartIcon />
              </Badge>
            </ListItemIcon>
            <ListItemText
              primary="Cart"
              secondary={`$${cartTotal.toFixed(2)}`}
              primaryTypographyProps={{ fontWeight: 600 }}
            />
          </ListItemButton>
        </Box>
        </Drawer>
      </Box>

      {/* Cart Drawer */}
      <CartDrawer open={cartDrawerOpen} onClose={() => setCartDrawerOpen(false)} />
    </>
  );
};

export default CustomSider;
