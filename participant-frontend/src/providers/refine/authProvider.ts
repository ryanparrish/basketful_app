/**
 * Auth Provider for Refine
 * Cookie-based JWT authentication with httpOnly cookies
 */
import type { AuthProvider } from '@refinedev/core';
import { apiClient } from '../../shared/api/secureClient';
import type { User, LoginRequest } from '../../shared/types/api';

const USER_STORAGE_KEY = 'basketful_user';

export interface LoginCredentials extends LoginRequest {
  recaptcha_token: string;
}

export const authProvider: AuthProvider = {
  login: async ({ customer_number, password, recaptcha_token }: LoginCredentials) => {
    try {
      const response = await apiClient.post('/auth/login/', {
        username: customer_number,
        password,
        recaptcha_token,
      });

      const { user } = response.data;
      
      // Store user info (tokens are in httpOnly cookies)
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));

      return {
        success: true,
        redirectTo: '/',
      };
    } catch (error: unknown) {
      const axiosError = error as { response?: { status: number; data?: { detail?: string; code?: string } } };
      const status = axiosError?.response?.status;
      const detail = axiosError?.response?.data?.detail;
      const code = axiosError?.response?.data?.code;
      
      let message = 'Login failed';
      if (code === 'recaptcha_failed') {
        message = detail || 'reCAPTCHA verification failed. Please try again.';
      } else if (status === 401) {
        message = detail || 'Invalid customer number or password';
      } else if (status === 429) {
        message = 'Too many login attempts. Please try again later.';
      } else if (detail) {
        message = detail;
      }

      return {
        success: false,
        error: {
          name: 'LoginError',
          message,
        },
      };
    }
  },

  logout: async () => {
    try {
      await apiClient.post('/auth/logout/');
    } catch {
      // Ignore logout errors - cookies cleared on backend anyway
    }
    
    localStorage.removeItem(USER_STORAGE_KEY);
    
    return {
      success: true,
      redirectTo: '/login',
    };
  },

  check: async () => {
    // First check if we have cached user data
    const storedUser = localStorage.getItem(USER_STORAGE_KEY);

    if (!storedUser) {
      return {
        authenticated: false,
        redirectTo: '/login',
        error: {
          message: 'No valid session',
          name: 'Unauthorized',
        },
      };
    }

    // Verify session is still valid by calling /auth/me/
    try {
      const response = await apiClient.get('/auth/me/');
      
      // Update cached user data with fresh data
      if (response.data.user) {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.data.user));
      }
      
      return {
        authenticated: true,
      };
    } catch {
      // Session invalid - clear cached data
      localStorage.removeItem(USER_STORAGE_KEY);
      
      return {
        authenticated: false,
        redirectTo: '/login?session_expired=true',
        error: {
          message: 'Session expired',
          name: 'Unauthorized',
        },
      };
    }
  },

  getIdentity: async (): Promise<User | null> => {
    const storedUser = localStorage.getItem(USER_STORAGE_KEY);
    if (storedUser) {
      try {
        return JSON.parse(storedUser) as User;
      } catch {
        return null;
      }
    }
    return null;
  },

  getPermissions: async () => {
    // Participants have standard permissions
    return ['participant'];
  },

  onError: async (error) => {
    const axiosError = error as { response?: { status: number; data?: { code?: string } } };
    const status = axiosError?.response?.status;
    const code = axiosError?.response?.data?.code;

    if (status === 401) {
      // Check if it's a session expiry
      const redirectTo = code === 'token_expired' 
        ? '/login?session_expired=true' 
        : '/login';
      
      return {
        logout: true,
        redirectTo,
        error,
      };
    }

    return { error };
  },
};

export default authProvider;
