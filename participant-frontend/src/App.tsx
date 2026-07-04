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
import { useTranslation } from 'react-i18next';
import { CartProvider } from './providers/CartProvider';
import { ValidationProvider } from './providers/ValidationContext';
import { AuthProvider } from './providers/AuthContext';
import { dataProvider, authProvider, i18nProvider } from './providers/refine';

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

// Inner layout — needs cart context, so must be inside AppProviders
const LayoutWithCart: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <>
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
    </>
  );
};

// Custom layout that wraps Refine's ThemedLayout
const CustomLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <AppProviders>
      <LayoutWithCart>{children}</LayoutWithCart>
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

// Refine wrapper — lives inside a component so resource labels re-render
// when the language changes
const RefineApp: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { t } = useTranslation();

  return (
    <Refine
      dataProvider={dataProvider}
      authProvider={authProvider}
      routerProvider={routerProvider}
      notificationProvider={useNotificationProvider}
      i18nProvider={i18nProvider}
      resources={[
        {
          name: 'products',
          list: '/products',
          meta: {
            label: t('nav.shop'),
            icon: <ShoppingCartIcon />,
          },
        },
        {
          name: 'checkout',
          list: '/checkout',
          meta: {
            label: t('nav.checkout'),
            icon: <PaymentIcon />,
          },
        },
        {
          name: 'orders',
          list: '/orders',
          meta: {
            label: t('nav.orderHistory'),
            icon: <ReceiptLongIcon />,
          },
        },
        {
          name: 'account',
          list: '/account',
          meta: {
            label: t('nav.myAccount'),
            icon: <AccountCircleIcon />,
          },
        },
      ]}
      options={{
        syncWithLocation: true,
        warnWhenUnsavedChanges: false,
      }}
    >
      {children}
    </Refine>
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
            <RefineApp>
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
          </RefineApp>
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
