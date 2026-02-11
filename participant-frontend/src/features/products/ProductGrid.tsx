/**
 * Product Grid Component
 * Responsive grid layout for products
 */
import React from 'react';
import { Grid, Box, Typography, Skeleton } from '@mui/material';
import type { Product } from '../../shared/types/api';
import { ProductCard } from './ProductCard';

interface ProductGridProps {
  products: Product[];
  isLoading?: boolean;
  emptyMessage?: string;
}

// Skeleton for loading state
const ProductSkeleton: React.FC = () => (
  <Box>
    <Skeleton variant="rectangular" height={140} sx={{ borderRadius: 1 }} />
    <Skeleton variant="text" sx={{ mt: 1 }} />
    <Skeleton variant="text" width="60%" />
    <Skeleton variant="text" width="40%" />
  </Box>
);

export const ProductGrid: React.FC<ProductGridProps> = ({
  products,
  isLoading = false,
  emptyMessage = 'No products available',
}) => {
  if (isLoading) {
    return (
      <Grid container spacing={3}>
        {[...Array(8)].map((_, index) => (
          <Grid
            key={`skeleton-${index}`}
            size={{ xs: 6, sm: 4, md: 3, lg: 3 }}
          >
            <ProductSkeleton />
          </Grid>
        ))}
      </Grid>
    );
  }

  if (products.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 200,
          p: 4,
        }}
      >
        <Typography variant="body1" color="text.secondary">
          {emptyMessage}
        </Typography>
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {products.map((product) => (
        <Grid
          key={product.id}
          size={{ xs: 6, sm: 4, md: 3, lg: 3 }}
        >
          <ProductCard product={product} />
        </Grid>
      ))}
    </Grid>
  );
};
