/**
 * API Endpoints - Typed functions for all API calls
 */
import { apiClient } from './secureClient';
import type {
  ThemeConfig,
  ProgramConfig,
  Category,
  Product,
  PaginatedResponse,
  ValidationRequest,
  ValidationResponse,
  RulesVersionResponse,
  OrderWindowStatus,
  Order,
  OrderListItem,
  CreateOrderRequest,
  CreateOrderResponse,
  ParticipantProfile,
} from '../types/api';

// Theme & Settings (public endpoints)
export const getThemeConfig = async (): Promise<ThemeConfig> => {
  const response = await apiClient.get('/settings/theme-config/');
  return response.data;
};

export const getProgramConfig = async (): Promise<ProgramConfig> => {
  const response = await apiClient.get('/settings/program-config/');
  return response.data;
};

// Rules Version
export const getRulesVersion = async (): Promise<RulesVersionResponse> => {
  const response = await apiClient.get('/rules/version/');
  return response.data;
};

// Order Window
export const getOrderWindow = async (): Promise<OrderWindowStatus> => {
  const response = await apiClient.get('/settings/order-window-status/');
  return response.data;
};

// Categories
export const getCategories = async (): Promise<Category[]> => {
  const response = await apiClient.get<PaginatedResponse<Category>>('/categories/');
  return response.data.results || response.data;
};

// Products
export const getProducts = async (params?: {
  category?: number;
  search?: string;
  active?: boolean;
}): Promise<Product[]> => {
  const response = await apiClient.get<PaginatedResponse<Product>>('/products/', {
    params: { ...params, active: true, page_size: 500 },
  });
  return response.data.results || response.data;
};

export const getProduct = async (id: number): Promise<Product> => {
  const response = await apiClient.get(`/products/${id}/`);
  return response.data;
};

// Validation
export const validateCart = async (data: ValidationRequest): Promise<ValidationResponse> => {
  const response = await apiClient.post('/orders/validate-cart/', data);
  return response.data;
};

// Orders
export const getOrders = async (): Promise<OrderListItem[]> => {
  const response = await apiClient.get<PaginatedResponse<OrderListItem>>('/orders/', {
    params: { page_size: 50 },
  });
  return response.data.results || response.data;
};

export const getOrder = async (id: number): Promise<Order> => {
  const response = await apiClient.get(`/orders/${id}/`);
  return response.data;
};

export const createOrder = async (data: CreateOrderRequest): Promise<CreateOrderResponse> => {
  const response = await apiClient.post('/orders/', data);
  return response.data;
};

export const confirmOrder = async (orderId: number): Promise<Order> => {
  const response = await apiClient.post(`/orders/${orderId}/confirm/`);
  return response.data;
};

// Participant Profile
export const getParticipantProfile = async (): Promise<ParticipantProfile> => {
  const response = await apiClient.get('/participants/me/');
  return response.data;
};

export const updateParticipantProfile = async (
  data: Partial<ParticipantProfile>
): Promise<ParticipantProfile> => {
  const response = await apiClient.patch('/participants/me/', data);
  return response.data;
};

// Balances
export const getAccountBalance = async (): Promise<{
  available_balance: number;
  hygiene_balance: number;
  go_fresh_balance: number;
}> => {
  const response = await apiClient.get('/account-balances/me/');
  return response.data;
};
