/**
 * Basketful Admin - Data Provider
 * 
 * Custom data provider that wraps ra-data-simple-rest with JWT authentication
 * and handles the Content-Range header for pagination.
 */
import type { DataProvider } from 'react-admin';
import { fetchUtils } from 'react-admin';
import simpleRestProvider from 'ra-data-simple-rest';
import { getAccessToken } from './authProvider';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * Custom HTTP client that adds JWT token to all requests
 */
const httpClient = async (url: string, options: fetchUtils.Options = {}) => {
  const token = await getAccessToken();
  
  const headers = new Headers(options.headers);
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return fetchUtils.fetchJson(url, { ...options, headers });
};

/**
 * Base data provider using simple-rest
 */
const baseDataProvider = simpleRestProvider(API_URL, httpClient);

/**
 * Custom data provider with enhanced functionality for Basketful
 */
export const dataProvider: DataProvider = {
  ...baseDataProvider,

  // Override getList to handle DRF pagination format
  getList: async (resource, params) => {
    const { page = 1, perPage = 25 } = params.pagination || {};
    const { field = 'id', order = 'ASC' } = params.sort || {};
    
    const query: Record<string, string> = {
      page: String(page),
      page_size: String(perPage),
      ordering: order === 'DESC' ? `-${field}` : field,
    };

    // Add filters
    if (params.filter) {
      Object.keys(params.filter).forEach((key) => {
        const value = params.filter[key];
        if (value !== undefined && value !== null && value !== '') {
          // Handle search filter specially
          if (key === 'q' || key === 'search') {
            query.search = value;
          } else {
            query[key] = String(value);
          }
        }
      });
    }

    const queryString = new URLSearchParams(query).toString();
    const url = `${API_URL}/${resource}/?${queryString}`;

    const { json, headers } = await httpClient(url);

    // Handle Content-Range header from DRF pagination
    const contentRange = headers.get('Content-Range');
    let total = json.count;
    
    if (contentRange) {
      const match = contentRange.match(/\/(\d+)$/);
      if (match) {
        total = parseInt(match[1], 10);
      }
    }

    return {
      data: json.results || json,
      total: total || (json.results?.length ?? json.length),
    };
  },

  // Override getOne to handle DRF format
  getOne: async (resource, params) => {
    const url = `${API_URL}/${resource}/${params.id}/`;
    const { json } = await httpClient(url);
    return { data: json };
  },

  // Override getMany to fetch multiple records by IDs
  getMany: async (resource, params) => {
    const queries = params.ids.map((id) =>
      httpClient(`${API_URL}/${resource}/${id}/`).then(({ json }) => json)
    );
    const results = await Promise.all(queries);
    return { data: results };
  },

  // Override getManyReference for related records
  getManyReference: async (resource, params) => {
    const { page, perPage } = params.pagination;
    const { field, order } = params.sort;

    const query: Record<string, string> = {
      page: String(page),
      page_size: String(perPage),
      ordering: order === 'DESC' ? `-${field}` : field,
      [params.target]: String(params.id),
    };

    // Add filters
    if (params.filter) {
      Object.keys(params.filter).forEach((key) => {
        const value = params.filter[key];
        if (value !== undefined && value !== null && value !== '') {
          query[key] = String(value);
        }
      });
    }

    const queryString = new URLSearchParams(query).toString();
    const url = `${API_URL}/${resource}/?${queryString}`;

    const { json, headers } = await httpClient(url);

    const contentRange = headers.get('Content-Range');
    let total = json.count;
    
    if (contentRange) {
      const match = contentRange.match(/\/(\d+)$/);
      if (match) {
        total = parseInt(match[1], 10);
      }
    }

    return {
      data: json.results || json,
      total: total || (json.results?.length ?? json.length),
    };
  },

  // Override create
  create: async (resource, params) => {
    const url = `${API_URL}/${resource}/`;
    const { json } = await httpClient(url, {
      method: 'POST',
      body: JSON.stringify(params.data),
    });
    return { data: json };
  },

  // Override update
  update: async (resource, params) => {
    const url = `${API_URL}/${resource}/${params.id}/`;
    const { json } = await httpClient(url, {
      method: 'PUT',
      body: JSON.stringify(params.data),
    });
    return { data: json };
  },

  // Override updateMany
  updateMany: async (resource, params) => {
    const queries = params.ids.map((id) =>
      httpClient(`${API_URL}/${resource}/${id}/`, {
        method: 'PUT',
        body: JSON.stringify(params.data),
      }).then(({ json }) => json.id)
    );
    const results = await Promise.all(queries);
    return { data: results };
  },

  // Override delete
  delete: async (resource, params) => {
    const url = `${API_URL}/${resource}/${params.id}/`;
    const { json } = await httpClient(url, { method: 'DELETE' });
    return { data: json || { id: params.id } };
  },

  // Override deleteMany
  deleteMany: async (resource, params) => {
    const queries = params.ids.map((id) =>
      httpClient(`${API_URL}/${resource}/${id}/`, {
        method: 'DELETE',
      }).then(() => id)
    );
    const results = await Promise.all(queries);
    return { data: results };
  },
};

export default dataProvider;
