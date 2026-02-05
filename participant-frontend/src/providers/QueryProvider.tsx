/**
 * TanStack Query Provider
 * Configures React Query with optimized defaults for mobile
 */
import React from 'react';
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

// Configure online manager to track network status
onlineManager.setEventListener((setOnline) => {
  const handleOnline = () => setOnline(true);
  const handleOffline = () => setOnline(false);

  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);

  // Initial state
  setOnline(navigator.onLine);

  return () => {
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
  };
});

// Create query client with mobile-optimized defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Retry failed requests up to 3 times
      retry: 3,
      // Wait before retrying (exponential backoff)
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      // Consider data fresh for 30 seconds
      staleTime: 30 * 1000,
      // Keep unused data in cache for 5 minutes
      gcTime: 5 * 60 * 1000,
      // Refetch on window focus (useful for returning to tab)
      refetchOnWindowFocus: true,
      // Don't refetch on reconnect by default (we handle this explicitly)
      refetchOnReconnect: true,
      // Network mode: always try to fetch but don't fail immediately offline
      networkMode: 'offlineFirst',
    },
    mutations: {
      // Retry mutations only once
      retry: 1,
      // Network mode for mutations
      networkMode: 'offlineFirst',
    },
  },
});

interface QueryProviderProps {
  children: React.ReactNode;
}

export const QueryProvider: React.FC<QueryProviderProps> = ({ children }) => {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
};

// Export for use in other parts of the app
export { queryClient };
