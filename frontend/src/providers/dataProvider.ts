/**
 * Basketful Admin - Data Provider
 * 
 * Custom data provider using Axios with cookie-based JWT authentication
 * and CSRF protection. No manual token management needed.
 */
import type { DataProvider } from 'react-admin';
import apiClient from '../lib/api/apiClient.js';

/**
 * Custom data provider with enhanced functionality for Basketful
 */
export const dataProvider: DataProvider = {
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
    const url = `/${resource}/?${queryString}`;

    const response = await apiClient.get(url);
    const json = response.data;

    // Handle Content-Range header from DRF pagination
    const contentRange = response.headers['content-range'];
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
    const url = `/${resource}/${params.id}/`;
    const response = await apiClient.get(url);
    return { data: response.data };
  },

  // Override getMany to fetch multiple records by IDs
  getMany: async (resource, params) => {
    const queries = params.ids.map((id) =>
      apiClient.get(`/${resource}/${id}/`).then((response: any) => response.data)
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
    const url = `/${resource}/?${queryString}`;

    const response = await apiClient.get(url);
    const json = response.data;

    const contentRange = response.headers['content-range'];
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
    const url = `/${resource}/`;
    const response = await apiClient.post(url, params.data);
    return { data: response.data };
  },

  // Override update — use PATCH so partial payloads (e.g. drag-to-reorder
  // sending only sort_order) are accepted by DRF without requiring every field.
  update: async (resource, params) => {
    const url = `/${resource}/${params.id}/`;
    const response = await apiClient.patch(url, params.data);
    return { data: response.data };
  },

  // Override updateMany — also PATCH for consistency
  updateMany: async (resource, params) => {
    const queries = params.ids.map((id) =>
      apiClient.patch(`/${resource}/${id}/`, params.data).then((response: any) => response.data.id)
    );
    const results = await Promise.all(queries);
    return { data: results };
  },

  // Override delete
  delete: async (resource, params) => {
    const url = `/${resource}/${params.id}/`;
    const response = await apiClient.delete(url);
    return { data: response.data || { id: params.id } };
  },

  // Override deleteMany
  deleteMany: async (resource, params) => {
    const queries = params.ids.map((id) =>
      apiClient.delete(`/${resource}/${id}/`).then(() => id)
    );
    const results = await Promise.all(queries);
    return { data: results };
  },
};

export default dataProvider;
