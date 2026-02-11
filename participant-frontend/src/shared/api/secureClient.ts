/**
 * Secure API Client with httpOnly Cookie-based JWT Authentication
 * 
 * Security features:
 * - Tokens stored in httpOnly cookies (XSS protection)
 * - CSRF protection via X-CSRFToken header
 * - Automatic token refresh on 401
 * - Session expiry handling
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Session expiry event for UI handling
export const SESSION_EXPIRED_EVENT = 'session-expired';

// Dispatch session expired event for UI components to handle
const dispatchSessionExpired = () => {
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
};

// Create axios instance - cookies sent automatically with credentials: 'include'
export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Always send cookies
});

// Get CSRF token from cookie
const getCsrfToken = (): string | null => {
  const csrfToken = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return csrfToken || null;
};

// Track if we're currently refreshing to avoid infinite loops
let isRefreshing = false;
let refreshSubscribers: ((success: boolean) => void)[] = [];

const onRefreshComplete = (success: boolean) => {
  refreshSubscribers.forEach((callback) => callback(success));
  refreshSubscribers = [];
};

const addRefreshSubscriber = (callback: (success: boolean) => void) => {
  refreshSubscribers.push(callback);
};

// Request interceptor - add CSRF token for mutations
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // Check if online
    if (!navigator.onLine) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      if (!navigator.onLine) {
        throw new Error('OFFLINE');
      }
    }

    // Add CSRF token for mutation requests
    if (config.method && ['post', 'put', 'patch', 'delete'].includes(config.method.toLowerCase())) {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken;
      }
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle 401 and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle 401 - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't retry refresh or login endpoints
      if (originalRequest.url?.includes('/auth/refresh') || originalRequest.url?.includes('/auth/login')) {
        dispatchSessionExpired();
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Wait for the refresh to complete
        return new Promise((resolve, reject) => {
          addRefreshSubscriber((success) => {
            if (success) {
              resolve(apiClient(originalRequest));
            } else {
              reject(error);
            }
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Try to refresh the token
        await axios.post(`${API_URL}/auth/refresh/`, {}, { withCredentials: true });
        isRefreshing = false;
        onRefreshComplete(true);
        
        // Retry the original request
        return apiClient(originalRequest);
      } catch (refreshError) {
        isRefreshing = false;
        onRefreshComplete(false);
        
        // Check if session expired
        const refreshAxiosError = refreshError as AxiosError<{ code?: string }>;
        if (refreshAxiosError.response?.data?.code === 'token_expired') {
          dispatchSessionExpired();
        }
        
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

// Auth helper functions (simplified for cookie-based auth)
export const auth = {
  login: async (username: string, password: string, recaptchaToken: string) => {
    const response = await apiClient.post('/auth/login/', {
      username,
      password,
      recaptcha_token: recaptchaToken,
    });
    return response.data;
  },

  logout: async () => {
    try {
      await apiClient.post('/auth/logout/');
    } catch {
      // Ignore errors on logout - cookies will be cleared anyway
    }
    window.location.href = '/login';
  },

  // Check authentication status by calling /auth/me/
  checkAuth: async () => {
    try {
      const response = await apiClient.get('/auth/me/');
      return response.data;
    } catch {
      return null;
    }
  },

  getUser: async () => {
    const response = await apiClient.get('/auth/me/');
    return response.data;
  },
};

// Legacy exports for backwards compatibility during migration
// These are no longer used with cookie-based auth but kept for smooth transition
const getAccessToken = (): string | null => null;
const getRefreshToken = (): string | null => null;
const setTokens = (_access: string, _refresh: string): void => {};
const clearTokens = (): void => {};

export { setTokens, clearTokens, getAccessToken, getRefreshToken };
