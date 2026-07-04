/**
 * Authentication Context
 * Manages user authentication state with httpOnly cookie-based JWT tokens
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { User, LoginRequest } from '../shared/types/api';
import { login as apiLogin, logout as apiLogout, refreshTokenRequest as apiRefresh, checkAuth } from '../shared/api/endpoints';
import { SESSION_EXPIRED_EVENT } from '../shared/api/secureClient';
import i18n from '../i18n';

// The participant's saved backend preference wins over the local
// (localStorage/browser) language once we know who they are.
const applyPreferredLanguage = (user: User | null) => {
  const preferredLanguage = user?.preferred_language;
  if (preferredLanguage && preferredLanguage !== i18n.language) {
    i18n.changeLanguage(preferredLanguage);
  }
};

/**
 * Login failures are stored as the backend's machine-readable code plus its
 * (server-translated) detail text. Rendering components translate the code
 * via the authErrors i18n namespace, so a language switch retranslates any
 * visible error.
 */
export interface AuthError {
  code: string;
  detail?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: AuthError | null;
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
            applyPreferredLanguage(user);
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
            applyPreferredLanguage(user);
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

      applyPreferredLanguage(response.user);

      // Invalidate queries to fetch fresh data
      queryClient.invalidateQueries();
      
      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err: any) {
      // Store the backend's machine-readable code; the login page translates
      // it at render time so it follows the active language
      const authError: AuthError = {
        code: err?.response?.data?.code || 'default',
        detail: err?.response?.data?.detail,
      };

      setState(prev => ({
        ...prev,
        isLoading: false,
        error: authError,
      }));
      throw new Error(authError.detail || authError.code);
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
