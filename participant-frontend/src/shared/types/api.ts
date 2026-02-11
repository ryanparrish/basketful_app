/**
 * API Types for Participant Frontend
 */

// Theme and Settings
export interface ThemeConfig {
  primary_color: string;
  secondary_color: string;
  logo: string | null;
  app_name: string;
  favicon: string | null;
  updated_at: string;
}

export interface ProgramConfig {
  grace_amount: number;
  grace_enabled: boolean;
  grace_message: string;
  rule_version: number;
  order_window_open: boolean;
  order_window_closes: string | null;
  grace_period_minutes: number;
  max_items_per_order: number | null;
  updated_at: string;
}

// Authentication
export interface User {
  id: number;
  username: string;
  email: string;
  participant_id: number;
  customer_number: string;
  name: string;
  first_name: string;
  last_name: string;
}

export interface TokenResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface LoginRequest {
  customer_number: string;
  password: string;
  recaptcha_token?: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

// Products and Categories
export interface Category {
  id: number;
  name: string;
  product_count: number;
}

export interface Product {
  id: number;
  name: string;
  description: string;
  price: number;
  image: string | null;
  category: number;
  category_name: string;
  is_available: boolean;
  unit: string | null;
}

// Cart and Validation
export interface CartItem {
  product_id: number;
  quantity: number;
}

export interface ValidationRequest {
  items: CartItem[];
}

export interface ValidationError {
  type: string;
  message: string;
  product_id?: number;
}

export interface Balances {
  available_balance: number;
  hygiene_balance: number;
  go_fresh_balance: number;
  total_voucher_amount: number;
  remaining_budget: number;
  total_budget: number;
  used_budget: number;
}

export interface ValidationResponse {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  balances: Balances;
}

// Orders
export interface OrderItem {
  id: number;
  product: number;
  product_id: number;
  product_name: string;
  quantity: number;
  price: number;
  total: number;
}

export interface Order {
  id: number;
  order_number: string;
  order_date: string;
  status: string;
  items: OrderItem[];
  total_price: number;
  total: number;
  created_at: string;
  notes?: string;
}

export interface CreateOrderRequest {
  items: CartItem[];
}

export interface CreateOrderResponse {
  id: number;
  order_number: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface RulesVersionResponse {
  rules_version: string;
}

export interface OrderWindowStatus {
  is_open: boolean;
  closes_at: string | null;
}

export interface OrderListItem {
  id: number;
  order_number: string;
  order_date: string;
  status: string;
  total_price: number;
  item_count: number;
  items?: OrderItem[];
  total?: number;
  created_at?: string;
  notes?: string;
}

export interface ParticipantProfile {
  id: number;
  customer_number: string;
  name: string;
  email: string;
}
