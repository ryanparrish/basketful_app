/**
 * Custom Data Provider for Django REST Framework
 * Handles Django's pagination format and API conventions
 */
import type { DataProvider, BaseRecord, GetListParams, GetOneParams, CreateParams, UpdateParams, DeleteOneParams, GetManyParams, CreateManyParams, UpdateManyParams, DeleteManyParams, CustomParams } from '@refinedev/core';
import { apiClient } from '../../shared/api/secureClient';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Map resource names to API endpoints
const resourceEndpoints: Record<string, string> = {
  products: '/products/',
  categories: '/categories/',
  orders: '/orders/',
  participants: '/participants/',
};

const getResourceEndpoint = (resource: string): string => {
  return resourceEndpoints[resource] || `/${resource}/`;
};

// Parse Django's pagination response format
interface DjangoPaginatedResponse<T = unknown> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

const isPaginated = <T>(data: unknown): data is DjangoPaginatedResponse<T> => {
  return (
    typeof data === 'object' &&
    data !== null &&
    'results' in data &&
    'count' in data
  );
};

export const dataProvider: DataProvider = {
  getList: async <TData extends BaseRecord = BaseRecord>({
    resource,
    pagination,
    sorters,
    filters,
    meta,
  }: GetListParams): Promise<{ data: TData[]; total: number }> => {
    const endpoint = getResourceEndpoint(resource);
    const { current = 1, pageSize = 10 } = pagination ?? {};

    // Build query params
    const params: Record<string, unknown> = {
      page: current,
      page_size: pageSize,
    };

    // Handle sorting - Django uses 'ordering' param
    if (sorters && sorters.length > 0) {
      const sortFields = sorters.map(s => 
        s.order === 'desc' ? `-${s.field}` : s.field
      );
      params.ordering = sortFields.join(',');
    }

    // Handle filters
    if (filters && filters.length > 0) {
      for (const filter of filters) {
        if ('field' in filter) {
          const { field, value, operator } = filter;
          if (operator === 'eq' || !operator) {
            params[field] = value;
          } else if (operator === 'contains') {
            params[`${field}__icontains`] = value;
          } else if (operator === 'in') {
            params[`${field}__in`] = Array.isArray(value) ? value.join(',') : value;
          }
        }
      }
    }

    // Add meta params (e.g., active: true for products)
    if (meta?.params) {
      Object.assign(params, meta.params);
    }

    const response = await apiClient.get(endpoint, { params });
    const data = response.data;

    if (isPaginated<TData>(data)) {
      return {
        data: data.results,
        total: data.count,
      };
    }

    // Handle non-paginated responses (arrays)
    return {
      data: Array.isArray(data) ? data : [data],
      total: Array.isArray(data) ? data.length : 1,
    };
  },

  getOne: async <TData extends BaseRecord = BaseRecord>({
    resource,
    id,
  }: GetOneParams): Promise<{ data: TData }> => {
    const endpoint = getResourceEndpoint(resource);
    const response = await apiClient.get(`${endpoint}${id}/`);
    return { data: response.data };
  },

  create: async <TData extends BaseRecord = BaseRecord, TVariables = object>({
    resource,
    variables,
  }: CreateParams<TVariables>): Promise<{ data: TData }> => {
    const endpoint = getResourceEndpoint(resource);
    const response = await apiClient.post(endpoint, variables);
    return { data: response.data };
  },

  update: async <TData extends BaseRecord = BaseRecord, TVariables = object>({
    resource,
    id,
    variables,
  }: UpdateParams<TVariables>): Promise<{ data: TData }> => {
    const endpoint = getResourceEndpoint(resource);
    const response = await apiClient.patch(`${endpoint}${id}/`, variables);
    return { data: response.data };
  },

  deleteOne: async <TData extends BaseRecord = BaseRecord, TVariables = object>({
    resource,
    id,
  }: DeleteOneParams<TVariables>): Promise<{ data: TData }> => {
    const endpoint = getResourceEndpoint(resource);
    const response = await apiClient.delete(`${endpoint}${id}/`);
    return { data: response.data };
  },

  getMany: async <TData extends BaseRecord = BaseRecord>({
    resource,
    ids,
  }: GetManyParams): Promise<{ data: TData[] }> => {
    const endpoint = getResourceEndpoint(resource);
    // Django doesn't have a native getMany, fetch individually
    const responses = await Promise.all(
      ids.map(id => apiClient.get(`${endpoint}${id}/`))
    );
    return { data: responses.map(r => r.data) };
  },

  createMany: async <TData extends BaseRecord = BaseRecord, TVariables = object>({
    resource,
    variables,
  }: CreateManyParams<TVariables>): Promise<{ data: TData[] }> => {
    const endpoint = getResourceEndpoint(resource);
    const responses = await Promise.all(
      variables.map(v => apiClient.post(endpoint, v))
    );
    return { data: responses.map(r => r.data) };
  },

  updateMany: async <TData extends BaseRecord = BaseRecord, TVariables = object>({
    resource,
    ids,
    variables,
  }: UpdateManyParams<TVariables>): Promise<{ data: TData[] }> => {
    const endpoint = getResourceEndpoint(resource);
    const responses = await Promise.all(
      ids.map(id => apiClient.patch(`${endpoint}${id}/`, variables))
    );
    return { data: responses.map(r => r.data) };
  },

  deleteMany: async <TData extends BaseRecord = BaseRecord, TVariables = object>({
    resource,
    ids,
  }: DeleteManyParams<TVariables>): Promise<{ data: TData[] }> => {
    const endpoint = getResourceEndpoint(resource);
    await Promise.all(ids.map(id => apiClient.delete(`${endpoint}${id}/`)));
    return { data: ids.map(id => ({ id } as unknown as TData)) };
  },

  custom: async <TData extends BaseRecord = BaseRecord, TQuery = unknown, TPayload = unknown>({
    url,
    method,
    payload,
    query,
    headers,
  }: CustomParams<TQuery, TPayload>): Promise<{ data: TData }> => {
    let response;
    const config = {
      params: query,
      headers,
    };

    switch (method) {
      case 'get':
        response = await apiClient.get(url, config);
        break;
      case 'post':
        response = await apiClient.post(url, payload, config);
        break;
      case 'put':
        response = await apiClient.put(url, payload, config);
        break;
      case 'patch':
        response = await apiClient.patch(url, payload, config);
        break;
      case 'delete':
        response = await apiClient.delete(url, config);
        break;
      default:
        response = await apiClient.get(url, config);
    }

    return { data: response.data };
  },

  getApiUrl: () => API_URL,
};

export default dataProvider;
