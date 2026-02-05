/**
 * Products Page
 * Main shopping page with category filtering and product grid
 */
import React, { useState, useMemo } from 'react';
import { Box, Container, Typography, Alert, TextField, InputAdornment } from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { getProducts, getCategories } from '../../shared/api/endpoints';
import { CategoryTabs } from './CategoryTabs';
import { ProductGrid } from './ProductGrid';
import { useOrderWindow } from '../../shared/hooks/useRuleVersion';
import { useCartValidation } from '../../shared/hooks/useCartValidation';
import type { Product } from '../../shared/types/api';

export const ProductsPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  const { isOpen: orderWindowOpen } = useOrderWindow();
  const { remainingBudget, isOverBudget } = useCartValidation();

  // Fetch products
  const {
    data: products = [],
    isLoading: productsLoading,
    error: productsError,
  } = useQuery({
    queryKey: ['products'],
    queryFn: getProducts,
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
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  return (
    <Box sx={{ pb: 10 }}>
      {/* Order Window Warning */}
      {!orderWindowOpen && (
        <Alert severity="warning" sx={{ borderRadius: 0 }}>
          The order window is currently closed. You can browse products but cannot place orders.
        </Alert>
      )}

      {/* Budget Warning */}
      {isOverBudget && (
        <Alert severity="error" sx={{ borderRadius: 0 }}>
          Your cart exceeds your available budget. Please remove some items.
        </Alert>
      )}

      {/* Budget Display */}
      {remainingBudget !== null && (
        <Box
          sx={{
            bgcolor: isOverBudget ? 'error.light' : 'primary.light',
            color: isOverBudget ? 'error.contrastText' : 'primary.contrastText',
            px: 2,
            py: 1,
            textAlign: 'center',
          }}
        >
          <Typography variant="body2">
            Budget Remaining: <strong>${remainingBudget.toFixed(2)}</strong>
          </Typography>
        </Box>
      )}

      {/* Search Bar */}
      <Container maxWidth="lg" sx={{ py: 2 }}>
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
      </Container>

      {/* Category Tabs */}
      <CategoryTabs
        categories={categories}
        selectedCategory={selectedCategory}
        onCategoryChange={handleCategoryChange}
        isLoading={categoriesLoading}
        productCounts={productCounts}
      />

      {/* Products Grid */}
      <Container maxWidth="lg" sx={{ py: 2 }}>
        {productsError ? (
          <Alert severity="error">
            Failed to load products. Please try again.
          </Alert>
        ) : (
          <>
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
      </Container>
    </Box>
  );
};

export default ProductsPage;
