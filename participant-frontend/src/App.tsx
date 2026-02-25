/**
 * Main App Component with Refine Integration
 * Professional shopping app with responsive layout
 */
import React from 'react';
import { Refine, Authenticated } from '@refinedev/core';
import { ThemedLayout, ErrorComponent, RefineSnackbarProvider, useNotificationProvider } from '@refinedev/mui';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import routerProvider, { CatchAllNavigate } from '@refinedev/react-router';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import PaymentIcon from '@mui/icons-material/Payment';

// Providers
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CartProvider } from './providers/CartProvider';
import { ValidationProvider } from './providers/ValidationContext';
import { AuthProvider } from './providers/AuthContext';
import { dataProvider, authProvider } from './providers/refine';

// Theme
import { useThemeConfig, defaultMuiTheme } from './shared/theme/dynamicTheme';

// Components
import { OfflineBanner } from './components/OfflineBanner';
import { CustomSider } from './components/refine/CustomSider';
import { CustomHeader } from './components/refine/CustomHeader';
import { AccountPage } from './components/AccountPage';
import { SessionExpiredDialog } from './components/SessionExpiredDialog';

// Features
import { LoginPage } from './features/auth';
import { ProductsPage } from './features/products';
import { CheckoutPage, OrderHistory } from './features/orders';

// Create a query client for TanStack Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

// Loading screen
const LoadingScreen: React.FC = () => (
  <Box
    sx={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      bgcolor: 'background.default',
    }}
  >
    <CircularProgress />
  </Box>
);

// Cart and validation wrapper for protected routes
const AppProviders: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <CartProvider>
    <ValidationProvider>
      {children}
    </ValidationProvider>
  </CartProvider>
);

// Custom layout that wraps Refine's ThemedLayout
const CustomLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <AppProviders>
      {/* Fixed header outside ThemedLayout to avoid double spacing */}
      <CustomHeader />
      <ThemedLayout
        Sider={() => <CustomSider />}
        Header={() => null}
        Footer={() => null}
        childrenBoxProps={{
          sx: {
            p: 0,
            pt: '64px', // Offset for fixed header
          },
        }}
      >
        {children}
      </ThemedLayout>
    </AppProviders>
  );
};

// Theme wrapper with dynamic theme
const ThemedApp: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { theme: dynamicTheme, isLoading } = useThemeConfig();

  // Use the dynamic MUI theme directly to avoid cross-version component type mismatches.
  const activeTheme = React.useMemo(() => {
    if (isLoading) return defaultMuiTheme;
    return dynamicTheme;
  }, [dynamicTheme, isLoading]);

  return (
    <ThemeProvider theme={activeTheme}>
      <CssBaseline />
      <RefineSnackbarProvider>
        {children}
      </RefineSnackbarProvider>
    </ThemeProvider>
  );
};

// Main app with Refine
const App: React.FC = () => {
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ThemedApp>
            <OfflineBanner />
            <SessionExpiredDialog />
            <Refine
            dataProvider={dataProvider}
            authProvider={authProvider}
            routerProvider={routerProvider}
            notificationProvider={useNotificationProvider}
            resources={[
              {
                name: 'products',
                list: '/products',
                meta: {
                  label: 'Shop',
                  icon: <ShoppingCartIcon />,
                },
              },
              {
                name: 'checkout',
                list: '/checkout',
                meta: {
                  label: 'Checkout',
                  icon: <PaymentIcon />,
                },
              },
              {
                name: 'orders',
                list: '/orders',
                meta: {
                  label: 'Order History',
                  icon: <ReceiptLongIcon />,
                },
              },
              {
                name: 'account',
                list: '/account',
                meta: {
                  label: 'My Account',
                  icon: <AccountCircleIcon />,
                },
              },
            ]}
            options={{
              syncWithLocation: true,
              warnWhenUnsavedChanges: false,
            }}
          >
            <Routes>
              {/* Public routes */}
              <Route path="/login" element={<LoginPage />} />

              {/* Protected routes with Refine layout */}
              <Route
                element={
                  <Authenticated
                    key="authenticated-routes"
                    fallback={<CatchAllNavigate to="/login" />}
                    loading={<LoadingScreen />}
                  >
                    <CustomLayout>
                      <Outlet />
                    </CustomLayout>
                  </Authenticated>
                }
              >
                <Route path="/products" element={<ProductsPage />} />
                <Route path="/checkout" element={<CheckoutPage />} />
                <Route path="/orders" element={<OrderHistory />} />
                <Route path="/account" element={<AccountPage />} />
              </Route>

              {/* Redirects */}
              <Route path="/" element={<Navigate to="/products" replace />} />
              <Route path="*" element={<ErrorComponent />} />
            </Routes>
          </Refine>
          </ThemedApp>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
};

export default App;

// Export context for backwards compatibility
export const DesktopLayoutContext = React.createContext<{
  isDesktop: boolean;
  showCart: boolean;
}>({
  isDesktop: false,
  showCart: false,
});
