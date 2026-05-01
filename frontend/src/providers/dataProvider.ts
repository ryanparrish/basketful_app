/**
 * Basketful Admin - Data Provider
 * 
 * Custom data provider using Axios with cookie-based JWT authentication
 * and CSRF protection. No manual token management needed.
 */
import type { DataProvider } from 'react-admin';
import apiClient from '../lib/api/apiClient.ts';

/**
 * If the data payload contains any React Admin file/image field objects
 * (shape: { rawFile: File, src: string }), convert the whole payload to
 * FormData so Django's ImageField / FileField can parse the upload.
 * All other scalar/array/object values are JSON-stringified into the form.
 */
function toFormDataIfNeeded(data: Record<string, unknown>): FormData | Record<string, unknown> {
  // Strip React Admin ImageInput empty/cleared values (e.g. { src: '', rawFile: undefined })
  // to avoid sending unparseable image descriptors as JSON to Django's ImageField.
  // Also strip empty strings so DRF field defaults (e.g. weight_lbs=0) can apply.
  const cleaned: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (
      value &&
      typeof value === 'object' &&
      !Array.isArray(value) &&
      !(value instanceof File) &&
      !(value as { rawFile?: unknown }).rawFile
    ) {
      // Object with no rawFile — likely a cleared or pre-existing ImageInput descriptor.
      // Skip it so we don't send { src: 'https://...' } as the image field value.
      continue;
    }
    // Skip empty strings so DRF field defaults kick in instead of rejecting ""
    if (value === '') continue;
    cleaned[key] = value;
  }

  const hasFile = Object.values(cleaned).some(
    (v) => v && typeof v === 'object' && (v as { rawFile?: unknown }).rawFile instanceof File
  );
  if (!hasFile) return cleaned;

  const form = new FormData();
  for (const [key, value] of Object.entries(cleaned)) {
    if (value === null || value === undefined) continue;
    if (value && typeof value === 'object' && (value as { rawFile?: unknown }).rawFile instanceof File) {
      form.append(key, (value as { rawFile: File }).rawFile);
    } else if (Array.isArray(value)) {
      // DRF accepts repeated keys for ManyToMany / array fields
      value.forEach((item) => form.append(key, String(item)));
    } else if (typeof value === 'object') {
      form.append(key, JSON.stringify(value));
    } else {
      form.append(key, String(value));
    }
  }
  return form;
}

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

    // Build base query params (non-array values)
    if (params.filter) {
      Object.keys(params.filter).forEach((key) => {
        const value = params.filter[key];
        if (value !== undefined && value !== null && value !== '') {
          if (key === 'q' || key === 'search') {
            query.search = value;
          } else if (!Array.isArray(value)) {
            // Scalar — store in the flat query object for URLSearchParams
            query[key] = String(value);
          }
          // Arrays are handled below via repeated params
        }
      });
    }

    // Build the query string, appending array filters as repeated keys
    // e.g. { account__participant__program: [1, 3] }
    // → account__participant__program=1&account__participant__program=3
    const params_ = new URLSearchParams(query);
    if (params.filter) {
      Object.keys(params.filter).forEach((key) => {
        const value = params.filter[key];
        if (Array.isArray(value) && value.length > 0) {
          value.forEach((v) => params_.append(key, String(v)));
        }
      });
    }
    const url = `/${resource}/?${params_.toString()}`;

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
    const body = toFormDataIfNeeded(params.data);
    let response;
    try {
      response = await apiClient.post(url, body);
    } catch (err: any) {
      // Log the full DRF error body so it's visible in the browser console
      console.error(`[dataProvider] POST ${url} failed:`, err?.response?.data ?? err);
      throw err;
    }
    const data = response.data;
    
    // Ensure the response has an id field for React-Admin
    if (!data.id) {
      console.error('Create response missing id:', data);
      throw new Error(`Invalid dataProvider response for create: missing id. Response: ${JSON.stringify(data)}`);
    }
    
    return { data };
  },

  // Override update — use PATCH so partial payloads (e.g. drag-to-reorder
  // sending only sort_order) are accepted by DRF without requiring every field.
  update: async (resource, params) => {
    const url = `/${resource}/${params.id}/`;
    const body = toFormDataIfNeeded(params.data);
    const response = await apiClient.patch(url, body);
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
