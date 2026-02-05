/**
 * Secure API Client with JWT Authentication
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance
export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Token management
const getAccessToken = (): string | null => {
  return localStorage.getItem('accessToken');
};

const getRefreshToken = (): string | null => {
  return localStorage.getItem('refreshToken');
};

const setTokens = (access: string, refresh: string): void => {
  localStorage.setItem('accessToken', access);
  localStorage.setItem('refreshToken', refresh);
};

const clearTokens = (): void => {
  localStorage.removeItem('accessToken');
  localStorage.removeItem('refreshToken');
};

// Check if token is expired
const isTokenExpired = (token: string): boolean => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    const { exp } = JSON.parse(jsonPayload);
    return exp * 1000 < Date.now();
  } catch {
    return true;
  }
};

// Refresh access token
const refreshAccessToken = async (): Promise<string | null> => {
  const refreshToken = getRefreshToken();
  if (!refreshToken || isTokenExpired(refreshToken)) {
    clearTokens();
    return null;
  }

  try {
    const response = await axios.post(`${API_URL}/token/refresh/`, {
      refresh: refreshToken,
    });
    const { access } = response.data;
    localStorage.setItem('accessToken', access);
    return access;
  } catch {
    clearTokens();
    return null;
  }
};

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // Check if online
    if (!navigator.onLine) {
      // Try once after 2 seconds
      await new Promise((resolve) => setTimeout(resolve, 2000));
      if (!navigator.onLine) {
        throw new Error('OFFLINE');
      }
    }

    let token = getAccessToken();

    // If token is expired, try to refresh
    if (token && isTokenExpired(token)) {
      token = await refreshAccessToken();
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Add CSRF token if available
    const csrfToken = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrftoken='))
      ?.split('=')[1];
    
    if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle 401 - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const newToken = await refreshAccessToken();
      
      if (newToken) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      }
      
      // Redirect to login
      window.location.href = '/login';
    }

    return Promise.reject(error);
  }
);

// Auth helper functions
export const auth = {
  login: async (username: string, password: string) => {
    const response = await axios.post(`${API_URL}/token/`, { username, password });
    const { access, refresh } = response.data;
    setTokens(access, refresh);
    return response.data;
  },

  logout: () => {
    clearTokens();
    window.location.href = '/login';
  },

  isAuthenticated: (): boolean => {
    const token = getAccessToken();
    return token !== null && !isTokenExpired(token);
  },

  getUser: async () => {
    const response = await apiClient.get('/users/me/');
    return response.data;
  },
};

export { setTokens, clearTokens, getAccessToken };
