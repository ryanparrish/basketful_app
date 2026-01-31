/**
 * Basketful Admin - Auth Provider
 * 
 * Handles JWT authentication with the Django REST Framework backend.
 */
import { AuthProvider } from 'react-admin';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

interface TokenResponse {
  access: string;
  refresh: string;
}

interface DecodedToken {
  exp: number;
  user_id: number;
  username: string;
}

// Helper to decode JWT payload
const decodeToken = (token: string): DecodedToken | null => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
};

// Check if token is expired
const isTokenExpired = (token: string): boolean => {
  const decoded = decodeToken(token);
  if (!decoded) return true;
  return decoded.exp * 1000 < Date.now();
};

// Refresh the access token using refresh token
const refreshAccessToken = async (): Promise<string | null> => {
  const refreshToken = localStorage.getItem('refreshToken');
  if (!refreshToken || isTokenExpired(refreshToken)) {
    return null;
  }

  try {
    const response = await fetch(`${API_URL}/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    localStorage.setItem('accessToken', data.access);
    return data.access;
  } catch {
    return null;
  }
};

export const authProvider: AuthProvider = {
  login: async ({ username, password }) => {
    const response = await fetch(`${API_URL}/token/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Invalid credentials');
    }

    const data: TokenResponse = await response.json();
    localStorage.setItem('accessToken', data.access);
    localStorage.setItem('refreshToken', data.refresh);
  },

  logout: () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    return Promise.resolve();
  },

  checkAuth: async () => {
    const accessToken = localStorage.getItem('accessToken');
    
    if (!accessToken) {
      throw new Error('No access token');
    }

    // If access token is expired, try to refresh
    if (isTokenExpired(accessToken)) {
      const newToken = await refreshAccessToken();
      if (!newToken) {
        throw new Error('Session expired');
      }
    }
  },

  checkError: (error) => {
    const status = error?.status || error?.response?.status;
    if (status === 401 || status === 403) {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      return Promise.reject();
    }
    return Promise.resolve();
  },

  getIdentity: async () => {
    const accessToken = localStorage.getItem('accessToken');
    if (!accessToken) {
      throw new Error('No access token');
    }

    const decoded = decodeToken(accessToken);
    if (!decoded) {
      throw new Error('Invalid token');
    }

    return {
      id: decoded.user_id,
      fullName: decoded.username,
    };
  },

  getPermissions: async () => {
    const accessToken = localStorage.getItem('accessToken');
    if (!accessToken) {
      return [];
    }

    const decoded = decodeToken(accessToken);
    if (!decoded) {
      return [];
    }

    // You can decode permissions from the token or fetch from API
    // For now, return empty - can be extended based on user roles
    return [];
  },
};

// Helper function to get current access token (with auto-refresh)
export const getAccessToken = async (): Promise<string | null> => {
  let accessToken = localStorage.getItem('accessToken');
  
  if (!accessToken) {
    return null;
  }

  if (isTokenExpired(accessToken)) {
    accessToken = await refreshAccessToken();
  }

  return accessToken;
};

export default authProvider;
