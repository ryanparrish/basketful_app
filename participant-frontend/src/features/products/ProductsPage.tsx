/**
 * Products Page
 * Main shopping page with responsive layout:
 * - Mobile: Horizontal category tabs
 * - Desktop: Uses Refine ThemedLayout sidebar for navigation
 */
import React, { useState, useMemo, useContext, useEffect } from 'react';
import { Box, Typography, Alert, TextField, InputAdornment, useMediaQuery, useTheme } from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { getProducts, getCategories } from '../../shared/api/endpoints';
import { CategoryTabs } from './CategoryTabs';
import { ProductGrid } from './ProductGrid';
import { useOrderWindow } from '../../shared/hooks/useRuleVersion';
import { useCartValidation } from '../../shared/hooks/useCartValidation';
import { DesktopLayoutContext } from '../../App';
import { CONTAINER_PADDING, useFullWidth } from '../../shared/constants/layout';

export const ProductsPage: React.FC = () => {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));
  // Context available for future cart visibility logic
  useContext(DesktopLayoutContext);
  
  // Read category from URL for integration with sidebar navigation
  const [searchParams, setSearchParams] = useSearchParams();
  const categoryFromUrl = searchParams.get('category');
  const [selectedCategory, setSelectedCategory] = useState<number | null>(
    categoryFromUrl ? parseInt(categoryFromUrl, 10) : null
  );
  const [searchQuery, setSearchQuery] = useState('');
  
  // Sync selectedCategory with URL params
  useEffect(() => {
    const urlCategory = searchParams.get('category');
    if (urlCategory) {
      setSelectedCategory(parseInt(urlCategory, 10));
    } else {
      setSelectedCategory(null);
    }
  }, [searchParams]);
  
  const { isOpen: orderWindowOpen } = useOrderWindow();
  const { isOverBudget } = useCartValidation();

  // Fetch products
  const {
    data: products = [],
    isLoading: productsLoading,
    error: productsError,
  } = useQuery({
    queryKey: ['products'],
    queryFn: () => getProducts(),
    staleTime: 60 * 1000, // 1 minute
  });

  // Fetch categories
  const {
    data: categories = [],
    isLoading: categoriesLoading,
  } = useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Calculate product counts per category
  const productCounts = useMemo(() => {
    const counts: Record<number, number> = {};
    products.forEach(product => {
      if (product.category) {
        counts[product.category] = (counts[product.category] || 0) + 1;
      }
    });
    return counts;
  }, [products]);

  // Filter products by category and search
  const filteredProducts = useMemo(() => {
    let filtered = products;

    // Filter by category
    if (selectedCategory !== null) {
      filtered = filtered.filter(p => p.category === selectedCategory);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(p =>
        p.name.toLowerCase().includes(query) ||
        p.description?.toLowerCase().includes(query) ||
        p.category_name?.toLowerCase().includes(query)
      );
    }

    // Sort: available first, then by name
    return filtered.sort((a, b) => {
      if (a.is_available !== b.is_available) {
        return a.is_available ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });
  }, [products, selectedCategory, searchQuery]);

  const handleCategoryChange = (categoryId: number | null) => {
    setSelectedCategory(categoryId);
    // Update URL params
    if (categoryId !== null) {
      setSearchParams({ category: String(categoryId) });
    } else {
      setSearchParams({});
    }
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  return (
    <>
      <Box sx={{ pb: { xs: 10, lg: 3 }, width: '100%' }}>
        {/* Alerts - full width */}
        {!orderWindowOpen && (
          <Alert severity="warning" sx={{ borderRadius: 0 }}>
            The order window is currently closed. You can browse products but cannot place orders.
          </Alert>
        )}

        {isOverBudget && (
          <Alert severity="error" sx={{ borderRadius: 0 }}>
            Your cart exceeds your available budget. Please remove some items.
          </Alert>
        )}

        {/* Desktop Layout: Content only (sidebar is in ThemedLayout) */}
        {isDesktop ? (
          <Box sx={{ px: 3, pt: 0, pb: 3, width: '100%' }}>
            {/* Search Bar */}
            <TextField
              fullWidth
              placeholder="Search products..."
              value={searchQuery}
              onChange={handleSearchChange}
              size="small"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon color="action" />
                  </InputAdornment>
                ),
              }}
              sx={{ mb: 3, maxWidth: 400 }}
            />

            {/* Results count */}
            {!productsLoading && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {filteredProducts.length} {filteredProducts.length === 1 ? 'product' : 'products'}
                {selectedCategory !== null && (
                  <> in {categories.find(c => c.id === selectedCategory)?.name}</>
                )}
                {searchQuery && <> matching "{searchQuery}"</>}
              </Typography>
            )}

            {productsError ? (
              <Alert severity="error">Failed to load products. Please try again.</Alert>
            ) : (
              <ProductGrid
                products={filteredProducts}
                isLoading={productsLoading}
                emptyMessage={
                  searchQuery
                    ? `No products found matching "${searchQuery}"`
                    : 'No products available in this category'
                }
              />
            )}
          </Box>
        ) : (
          /* Mobile Layout: Tabs + Grid */
          <>
            <Box sx={{ 
              ...useFullWidth(),
              py: 2, 
              px: CONTAINER_PADDING 
            }}>
              <TextField
                fullWidth
                placeholder="Search products..."
                value={searchQuery}
                onChange={handleSearchChange}
                size="small"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon color="action" />
                    </InputAdornment>
                  ),
                }}
                sx={{ mb: 2 }}
              />
            </Box>

            <CategoryTabs
              categories={categories}
              selectedCategory={selectedCategory}
              onCategoryChange={handleCategoryChange}
              isLoading={categoriesLoading}
              productCounts={productCounts}
            />

            <Box sx={{ 
              ...useFullWidth(),
              py: 2, 
              px: CONTAINER_PADDING 
            }}>
              {productsError ? (
                <Alert severity="error">Failed to load products. Please try again.</Alert>
              ) : (
                <>
                  {!productsLoading && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {filteredProducts.length} {filteredProducts.length === 1 ? 'product' : 'products'}
                      {selectedCategory !== null && (
                        <> in {categories.find(c => c.id === selectedCategory)?.name}</>
                      )}
                      {searchQuery && <> matching "{searchQuery}"</>}
                    </Typography>
                  )}

                  <ProductGrid
                    products={filteredProducts}
                    isLoading={productsLoading}
                    emptyMessage={
                      searchQuery
                        ? `No products found matching "${searchQuery}"`
                        : 'No products available in this category'
                    }
                  />
                </>
              )}
            </Box>
          </>
        )}
    </Box>
    </>
  );
};

export default ProductsPage;
