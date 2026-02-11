/**
 * Main App Component
 * Sets up routing and providers with responsive desktop/mobile layouts
 */
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, CircularProgress, useMediaQuery, useTheme } from '@mui/material';

// Providers
import { QueryProvider } from './providers/QueryProvider';
import { AuthProvider, useAuth } from './providers/AuthContext';
import { CartProvider } from './providers/CartProvider';
import { ValidationProvider } from './providers/ValidationContext';

// Theme
import { useThemeConfig, defaultMuiTheme } from './shared/theme/dynamicTheme';

// Components
import { OfflineBanner } from './components/OfflineBanner';
import { BottomNavigation } from './components/BottomNavigation';
import { AppHeader } from './components/AppHeader';
import { AccountPage } from './components/AccountPage';

// Features
import { LoginPage } from './features/auth';
import { ProductsPage } from './features/products';
import { CheckoutPage, OrderHistory } from './features/orders';

// Layout constants
import { DESKTOP_SIDEBAR_WIDTH } from './shared/constants/layout';

// Context for desktop layout state
export const DesktopLayoutContext = React.createContext<{
  isDesktop: boolean;
  showCart: boolean;
}>({
  isDesktop: false,
  showCart: false,
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

// Protected route wrapper
const ProtectedRoute: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};

// Layout with header and responsive nav
const AppLayout: React.FC = () => {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));

  return (
    <CartProvider>
      <ValidationProvider>
        <DesktopLayoutContext.Provider value={{ isDesktop, showCart: false }}>
          <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', overflowX: 'hidden' }}>
            <AppHeader />
            
            {/* Main content area - full width */}
            <Box 
              component="main"
              sx={{
                width: '100%',
                maxWidth: '100%',
              }}
            >
              <Outlet />
            </Box>
            
            {/* Bottom navigation for mobile */}
            {!isDesktop && <BottomNavigation />}
          </Box>
        </DesktopLayoutContext.Provider>
      </ValidationProvider>
    </CartProvider>
  );
};

// Theme wrapper with dynamic theme
const ThemedApp: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { theme, isLoading } = useThemeConfig();

  // Use default theme while loading
  const activeTheme = isLoading ? defaultMuiTheme : theme;

  return (
    <ThemeProvider theme={activeTheme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
};

// Main app with routing
const AppRoutes: React.FC = () => {
  return (
    <BrowserRouter>
      <OfflineBanner />
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/checkout" element={<CheckoutPage />} />
            <Route path="/orders" element={<OrderHistory />} />
            <Route path="/account" element={<AccountPage />} />
          </Route>
        </Route>

        {/* Redirect root to products */}
        <Route path="/" element={<Navigate to="/products" replace />} />
        
        {/* Catch all - redirect to products */}
        <Route path="*" element={<Navigate to="/products" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

// Root app component
const App: React.FC = () => {
  return (
    <QueryProvider>
      <AuthProvider>
        <ThemedApp>
          <AppRoutes />
        </ThemedApp>
      </AuthProvider>
    </QueryProvider>
  );
};

export default App;
