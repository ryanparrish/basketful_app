/**
 * Basketful Admin - Auth Provider
 * 
 * Handles httpOnly cookie-based JWT authentication with the Django REST Framework backend.
 * Security features:
 * - Tokens stored in httpOnly cookies (XSS protection)
 * - No token storage in localStorage
 * - CSRF protection via X-CSRFToken header
 * - Automatic token refresh on 401
 */
import type { AuthProvider } from 'react-admin';
import apiClient from '../lib/api/apiClient.ts';

const USER_STORAGE_KEY = 'basketful_admin_user';

interface LoginCredentials {
  username: string;
  password: string;
  recaptcha_token: string;
}

interface UserData {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  is_superuser: boolean;
  groups?: string[];
  group_ids?: number[];
}

interface UserResponse {
  user: UserData;
  message?: string;
}

export const authProvider: AuthProvider = {
  login: async ({ username, password, recaptcha_token }: LoginCredentials) => {
    try {
      const response = await apiClient.post<UserResponse>('/auth/login/', {
        username,
        password,
        recaptcha_token,
      });

      const { user } = response.data;

      // Store only user metadata (NOT tokens - they're in httpOnly cookies)
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));

      return Promise.resolve();
    } catch (error: any) {
      console.error('Login error:', error);
      
      // Pass through the error for the login page to handle
      return Promise.reject(error);
    }
  },

  logout: async () => {
    try {
      await apiClient.post('/auth/logout/');
    } catch (error) {
      // Ignore errors on logout - cookies will be cleared anyway
      console.error('Logout error:', error);
    }

    // Clear cached user data
    localStorage.removeItem(USER_STORAGE_KEY);
    localStorage.removeItem('userPermissions');
    localStorage.removeItem('permissionsCacheTime');

    return Promise.resolve();
  },

  checkAuth: async () => {
    const storedUser = localStorage.getItem(USER_STORAGE_KEY);

    if (!storedUser) {
      return Promise.reject();
    }

    // Verify session by calling /auth/me/
    try {
      const response = await apiClient.get<UserResponse>('/auth/me/');

      // Update cached user data
      if (response.data.user) {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.data.user));
      }

      return Promise.resolve();
    } catch (error) {
      // Session expired or invalid
      localStorage.removeItem(USER_STORAGE_KEY);
      return Promise.reject();
    }
  },

  checkError: (error) => {
    const status = error?.status || error?.response?.status;
    if (status === 401 || status === 403) {
      localStorage.removeItem(USER_STORAGE_KEY);
      localStorage.removeItem('userPermissions');
      localStorage.removeItem('permissionsCacheTime');
      return Promise.reject();
    }
    return Promise.resolve();
  },

  getIdentity: async () => {
    const storedUser = localStorage.getItem(USER_STORAGE_KEY);
    
    if (!storedUser) {
      throw new Error('No user data');
    }

    try {
      const user: UserData = JSON.parse(storedUser);

      return {
        id: user.id,
        fullName: user.username,
        email: user.email,
      };
    } catch {
      throw new Error('Invalid user data');
    }
  },

  getPermissions: async () => {
    const storedUser = localStorage.getItem(USER_STORAGE_KEY);
    
    if (!storedUser) {
      return null;
    }

    try {
      const user: UserData = JSON.parse(storedUser);

      // Check if we have cached permissions (less than 30 minutes old)
      const cachedPermissions = localStorage.getItem('userPermissions');
      const cacheTimestamp = localStorage.getItem('permissionsCacheTime');

      if (cachedPermissions && cacheTimestamp) {
        const cacheAge = Date.now() - parseInt(cacheTimestamp);
        const THIRTY_MINUTES = 30 * 60 * 1000;

        if (cacheAge < THIRTY_MINUTES) {
          return JSON.parse(cachedPermissions);
        }
      }

      // Fetch fresh permissions from API
      try {
        const response = await apiClient.get('/users/me/permissions/');
        const permissions = response.data;

        // Cache the permissions
        localStorage.setItem('userPermissions', JSON.stringify(permissions));
        localStorage.setItem('permissionsCacheTime', Date.now().toString());

        return permissions;
      } catch (error) {
        console.error('Error fetching permissions:', error);
        // Fall back to user data
        return {
          groups: user.groups || [],
          group_ids: user.group_ids || [],
          is_staff: user.is_staff || false,
          is_superuser: user.is_superuser || false,
          permissions: [],
        };
      }
    } catch {
      return null;
    }
  },
};

export default authProvider;
