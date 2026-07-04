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
  preferred_language?: string | null;
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
  severity?: 'error' | 'warning';
  product_id?: number;
  amount_over?: number;
  grace_allowed?: boolean;
}

export interface Balances {
  available_balance: number;
  hygiene_balance: number;
  go_fresh_balance: number;
  full_balance: number;
}

export interface ValidationResponse {
  valid: boolean;
  violations: ValidationError[];
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

export type WindowStatusCode =
  | 'open'
  | 'closed'
  | 'force_open'
  | 'force_closed'
  | 'disabled'
  | 'no_schedule';

export interface ParticipantWindowStatus {
  is_open: boolean;
  window_status: WindowStatusCode;
  seconds_until_change: number | null;
  next_opens_at: string | null;
  next_closes_at: string | null;
  program_name: string;
  override_reason: string | null;
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

export interface ParticipantProgram {
  id: number;
  name: string;
  meeting_day: string;
  meeting_time: string;
  meeting_address: string;
}

export interface ParticipantCoach {
  id: number;
  name: string;
  email: string;
  phone_number: string;
  image: string | null;
}

export interface ParticipantMeProfile {
  name: string;
  customer_number: string;
  preferred_language: string;
  program: ParticipantProgram | null;
  coach: ParticipantCoach | null;
}
