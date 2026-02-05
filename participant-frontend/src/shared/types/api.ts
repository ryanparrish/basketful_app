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
}

export interface TokenResponse {
  access: string;
  refresh: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

// Products and Categories
export interface Category {
  id: number;
  name: string;
  product_count: number;
}

export interface Subcategory {
  id: number;
  name: string;
  category: number;
  category_name: string;
}

export interface Product {
  id: number;
  name: string;
  description: string;
  price: number;
  image: string | null;
  category: number;
  category_name: string;
  subcategory: number | null;
  subcategory_name: string | null;
  quantity_in_stock: number;
  active: boolean;
  is_meat: boolean;
  weight_lbs: number | null;
  tags: Tag[];
}

export interface Tag {
  id: number;
  name: string;
  slug: string;
}

// Cart and Validation
export interface CartItem {
  id: string;
  product_id: number;
  name: string;
  price: number;
  quantity: number;
  image?: string | null;
  category_name?: string;
}

export interface ValidationRequest {
  participant_id: number;
  items: Array<{
    product_id: number;
    quantity: number;
  }>;
}

export interface ValidationViolation {
  type: 'limit' | 'balance' | 'stock' | 'window';
  severity: 'error' | 'warning';
  message: string;
  amount_over?: number;
  grace_allowed?: boolean;
  category_name?: string;
  product_name?: string;
}

export interface CategoryLimit {
  category_id: number;
  category_name: string;
  subcategory_id?: number;
  subcategory_name?: string;
  used: number;
  max: number;
  scope: 'per_adult' | 'per_child' | 'per_infant' | 'per_household' | 'per_order';
}

export interface Balances {
  available_balance: number;
  hygiene_balance: number;
  go_fresh_balance: number;
  total_voucher_amount: number;
}

export interface ValidationResponse {
  valid: boolean;
  violations: ValidationViolation[];
  balances: Balances;
  limits: CategoryLimit[];
  rules_version: string;
  cart_total: number;
}

export interface RulesVersionResponse {
  rules_version: string;
}

// Order Window
export interface OrderWindowStatus {
  id: number;
  hours_before_class: number;
  hours_before_close: number;
  enabled: boolean;
  is_open: boolean;
  opens_at: string | null;
  closes_at: string | null;
  next_class_time: string | null;
}

// Orders
export interface OrderItem {
  id: number;
  product: number;
  product_name: string;
  product_category: string;
  quantity: number;
  price: number;
  price_at_order: number;
  total: number;
}

export interface Order {
  id: number;
  order_number: string;
  account: number;
  participant_name: string;
  participant_customer_number: string;
  program_name: string;
  order_date: string;
  status: 'pending' | 'confirmed' | 'packing' | 'completed' | 'cancelled';
  paid: boolean;
  go_fresh_total: number;
  items: OrderItem[];
  total_price: number;
  is_combined: boolean;
  validation_logs: ValidationLog[];
  created_at: string;
  updated_at: string;
}

export interface OrderListItem {
  id: number;
  order_number: string;
  participant_name: string;
  participant_customer_number: string;
  status: Order['status'];
  paid: boolean;
  total_price: number;
  item_count: number;
  order_date: string;
  created_at: string;
}

export interface ValidationLog {
  id: number;
  order: number;
  error_message: string;
  created_at: string;
}

export interface CreateOrderRequest {
  account: number;
  items: Array<{
    product: number;
    quantity: number;
  }>;
}

export interface CreateOrderResponse {
  id: number;
  order_number: string;
}

// Participant Profile
export interface ParticipantProfile {
  id: number;
  customer_number: string;
  name: string;
  email: string;
  phone_number: string;
  program: number;
  program_name: string;
  active: boolean;
  adults: number;
  children: number;
  infants: number;
  dietary_restrictions: string;
  account_balance_id: number;
  available_balance: number;
  hygiene_balance: number;
  go_fresh_balance: number;
}

// API Response wrappers
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
