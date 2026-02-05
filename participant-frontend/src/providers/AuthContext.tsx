/**
 * Authentication Context
 * Manages user authentication state with JWT tokens
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { User, LoginRequest, AuthTokens } from '../shared/types/api';
import { login as apiLogin, logout as apiLogout, refreshToken as apiRefresh, getBalances } from '../shared/api/endpoints';
import { setTokens, getAccessToken, getRefreshToken, clearTokens } from '../shared/api/secureClient';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

// Token storage keys
const USER_STORAGE_KEY = 'basketful_user';

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  // Initialize auth state from storage
  useEffect(() => {
    const initAuth = async () => {
      const accessToken = getAccessToken();
      const refreshTokenValue = getRefreshToken();
      const storedUser = localStorage.getItem(USER_STORAGE_KEY);

      if (accessToken && storedUser) {
        try {
          const user = JSON.parse(storedUser) as User;
          // Verify token is still valid by fetching balances
          await getBalances();
          setState({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } catch {
          // Token might be expired, try refresh
          if (refreshTokenValue) {
            try {
              const tokens = await apiRefresh(refreshTokenValue);
              setTokens(tokens.access, tokens.refresh || refreshTokenValue);
              const user = JSON.parse(storedUser) as User;
              setState({
                user,
                isAuthenticated: true,
                isLoading: false,
                error: null,
              });
            } catch {
              // Refresh failed, clear everything
              clearTokens();
              localStorage.removeItem(USER_STORAGE_KEY);
              setState({
                user: null,
                isAuthenticated: false,
                isLoading: false,
                error: null,
              });
            }
          } else {
            clearTokens();
            localStorage.removeItem(USER_STORAGE_KEY);
            setState({
              user: null,
              isAuthenticated: false,
              isLoading: false,
              error: null,
            });
          }
        }
      } else {
        setState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      }
    };

    initAuth();
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      const response = await apiLogin(credentials);
      
      // Store tokens
      setTokens(response.access, response.refresh);
      
      // Store user info
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.user));
      
      // Invalidate queries to fetch fresh data
      queryClient.invalidateQueries();
      
      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      throw err;
    }
  }, [queryClient]);

  const logout = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true }));
    
    try {
      const refreshTokenValue = getRefreshToken();
      if (refreshTokenValue) {
        await apiLogout(refreshTokenValue);
      }
    } catch {
      // Ignore logout errors, still clear local state
    } finally {
      clearTokens();
      localStorage.removeItem(USER_STORAGE_KEY);
      queryClient.clear();
      
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  }, [queryClient]);

  const refreshUser = useCallback(async () => {
    const refreshTokenValue = getRefreshToken();
    if (!refreshTokenValue) {
      throw new Error('No refresh token available');
    }

    try {
      const tokens = await apiRefresh(refreshTokenValue);
      setTokens(tokens.access, tokens.refresh || refreshTokenValue);
    } catch (err) {
      // Refresh failed, log out
      await logout();
      throw err;
    }
  }, [logout]);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  const value = useMemo<AuthContextType>(() => ({
    ...state,
    login,
    logout,
    refreshUser,
    clearError,
  }), [state, login, logout, refreshUser, clearError]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// HOC for protected routes
export const withAuth = <P extends object>(
  WrappedComponent: React.ComponentType<P>
): React.FC<P> => {
  const WithAuthComponent: React.FC<P> = (props) => {
    const { isAuthenticated, isLoading } = useAuth();
    
    if (isLoading) {
      return null; // Or a loading spinner
    }
    
    if (!isAuthenticated) {
      return null; // Let router handle redirect
    }
    
    return <WrappedComponent {...props} />;
  };
  
  WithAuthComponent.displayName = `withAuth(${WrappedComponent.displayName || WrappedComponent.name})`;
  
  return WithAuthComponent;
};
