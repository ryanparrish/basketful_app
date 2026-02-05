/**
 * Category Tabs Component
 * Horizontal scrollable category filter
 */
import React from 'react';
import { Tabs, Tab, Box, Chip, Skeleton } from '@mui/material';
import type { Category } from '../../shared/types/api';

interface CategoryTabsProps {
  categories: Category[];
  selectedCategory: number | null;
  onCategoryChange: (categoryId: number | null) => void;
  isLoading?: boolean;
  productCounts?: Record<number, number>;
}

export const CategoryTabs: React.FC<CategoryTabsProps> = ({
  categories,
  selectedCategory,
  onCategoryChange,
  isLoading = false,
  productCounts,
}) => {
  const handleChange = (_event: React.SyntheticEvent, newValue: number | 'all') => {
    onCategoryChange(newValue === 'all' ? null : newValue);
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', gap: 1, p: 1, overflowX: 'auto' }}>
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} variant="rounded" width={80} height={32} />
        ))}
      </Box>
    );
  }

  if (categories.length === 0) {
    return null;
  }

  const value = selectedCategory ?? 'all';

  return (
    <Box
      sx={{
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      <Tabs
        value={value}
        onChange={handleChange}
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        aria-label="Category filter"
        sx={{
          '& .MuiTab-root': {
            minHeight: 48,
            textTransform: 'none',
          },
        }}
      >
        <Tab
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <span>All</span>
              {productCounts && (
                <Chip
                  size="small"
                  label={Object.values(productCounts).reduce((a, b) => a + b, 0)}
                  sx={{ height: 20, fontSize: '0.75rem' }}
                />
              )}
            </Box>
          }
          value="all"
        />
        {categories.map((category) => (
          <Tab
            key={category.id}
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <span>{category.name}</span>
                {productCounts?.[category.id] !== undefined && (
                  <Chip
                    size="small"
                    label={productCounts[category.id]}
                    sx={{ height: 20, fontSize: '0.75rem' }}
                  />
                )}
              </Box>
            }
            value={category.id}
          />
        ))}
      </Tabs>
    </Box>
  );
};
