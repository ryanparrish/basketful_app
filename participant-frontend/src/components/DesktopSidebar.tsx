/**
 * Desktop Category Sidebar
 * Left sidebar for category navigation on desktop
 */
import React from 'react';
import {
  Box,
  List,
  ListItemButton,
  ListItemText,
  Typography,
  Chip,
  Divider,
  Skeleton,
} from '@mui/material';
import { Category as CategoryIcon } from '@mui/icons-material';
import type { Category } from '../shared/types/api';


interface DesktopSidebarProps {
  categories: Category[];
  selectedCategory: number | null;
  onCategoryChange: (categoryId: number | null) => void;
  isLoading?: boolean;
  productCounts?: Record<number, number>;
}

export const DesktopSidebar: React.FC<DesktopSidebarProps> = ({
  categories,
  selectedCategory,
  onCategoryChange,
  isLoading = false,
  productCounts = {},
}) => {
  const totalProducts = Object.values(productCounts).reduce((a, b) => a + b, 0);

  if (isLoading) {
    return (
      <Box sx={{ p: 2 }}>
        <Skeleton variant="text" width={120} height={28} sx={{ mb: 2 }} />
        {[...Array(6)].map((_, i) => (
          <Skeleton key={i} variant="rounded" height={40} sx={{ mb: 1 }} />
        ))}
      </Box>
    );
  }

  return (
    <Box sx={{ py: 2 }}>
      <Box sx={{ px: 2, mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        <CategoryIcon color="primary" fontSize="small" />
        <Typography variant="subtitle2" color="text.secondary" fontWeight={600}>
          CATEGORIES
        </Typography>
      </Box>
      
      <List dense disablePadding>
        {/* All Products */}
        <ListItemButton
          selected={selectedCategory === null}
          onClick={() => onCategoryChange(null)}
          sx={{ py: 1.5, px: 2 }}
        >
          <ListItemText 
            primary="All Products" 
            primaryTypographyProps={{ fontWeight: selectedCategory === null ? 600 : 400 }}
          />
          <Chip 
            size="small" 
            label={totalProducts} 
            sx={{ height: 22, fontSize: '0.75rem' }}
          />
        </ListItemButton>

        <Divider sx={{ my: 1 }} />

        {/* Category Items */}
        {categories.map((category) => (
          <ListItemButton
            key={category.id}
            selected={selectedCategory === category.id}
            onClick={() => onCategoryChange(category.id)}
            sx={{ py: 1.5, px: 2 }}
          >
            <ListItemText 
              primary={category.name}
              primaryTypographyProps={{ 
                fontWeight: selectedCategory === category.id ? 600 : 400,
                noWrap: true,
              }}
            />
            {productCounts[category.id] !== undefined && (
              <Chip 
                size="small" 
                label={productCounts[category.id]} 
                sx={{ height: 22, fontSize: '0.75rem' }}
              />
            )}
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
};

export default DesktopSidebar;
