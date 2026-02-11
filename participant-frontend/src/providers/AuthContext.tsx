/**
 * Authentication Context
 * Manages user authentication state with httpOnly cookie-based JWT tokens
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { User, LoginRequest } from '../shared/types/api';
import { login as apiLogin, logout as apiLogout, refreshTokenRequest as apiRefresh, checkAuth } from '../shared/api/endpoints';
import { SESSION_EXPIRED_EVENT } from '../shared/api/secureClient';

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

// User storage key (only stores user info, not tokens - tokens are in httpOnly cookies)
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

  // Initialize auth state by checking with server
  useEffect(() => {
    const initAuth = async () => {
      const storedUser = localStorage.getItem(USER_STORAGE_KEY);

      if (storedUser) {
        try {
          // Verify session is still valid by calling auth/me endpoint
          const authStatus = await checkAuth();
          if (authStatus.is_authenticated) {
            const user = JSON.parse(storedUser) as User;
            setState({
              user,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });
            return;
          }
        } catch {
          // Try to refresh the token
          try {
            await apiRefresh(''); // Token is read from cookie
            const user = JSON.parse(storedUser) as User;
            setState({
              user,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });
            return;
          } catch {
            // Refresh failed, clear user data
            localStorage.removeItem(USER_STORAGE_KEY);
          }
        }
      }
      
      // Not authenticated
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    };

    initAuth();
  }, []);

  // Listen for session expired events
  useEffect(() => {
    const handleSessionExpired = () => {
      localStorage.removeItem(USER_STORAGE_KEY);
      queryClient.clear();
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    };

    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, [queryClient]);

  const login = useCallback(async (credentials: LoginRequest) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      const response = await apiLogin(credentials);
      
      // Tokens are now stored in httpOnly cookies by the server
      // Only store user info in localStorage
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.user));
      
      // Invalidate queries to fetch fresh data
      queryClient.invalidateQueries();
      
      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: any) {
      // Extract error code and detail from backend response
      const errorCode = err?.response?.data?.code;
      const errorDetail = err?.response?.data?.detail;
      
      // Map backend error codes to user-friendly messages
      let errorMessage = 'Login failed. Please try again.';
      
      switch (errorCode) {
        case 'customer_not_found':
          errorMessage = 'Customer number not found. Please check and try again.';
          break;
        case 'username_not_found':
          errorMessage = 'Username not found. Please check and try again.';
          break;
        case 'no_user_account':
          errorMessage = 'No user account is linked to this customer number. Please contact support.';
          break;
        case 'invalid_password':
          errorMessage = 'Incorrect password. Please try again.';
          break;
        case 'account_disabled':
          errorMessage = 'Your account has been disabled. Please contact support.';
          break;
        case 'recaptcha_required':
          errorMessage = 'Please complete the security verification.';
          break;
        case 'recaptcha_failed':
          errorMessage = 'Security verification failed. Please try again.';
          break;
        default:
          errorMessage = errorDetail || (err instanceof Error ? err.message : 'Login failed. Please try again.');
      }
      
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));
      throw new Error(errorMessage);
    }
  }, [queryClient]);

  const logout = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true }));
    
    try {
      // Call logout endpoint - server will clear cookies and blacklist tokens
      await apiLogout('');
    } catch {
      // Ignore logout errors, still clear local state
    } finally {
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
    try {
      // Token is read from httpOnly cookie by the server
      await apiRefresh('');
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
