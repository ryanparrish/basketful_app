export interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

export interface OrderWindowSettings {
  id: number;
  hours_before_class: number;
  hours_before_close: number;
  enabled: boolean;
  is_open: boolean;
  next_opens_at: string | null;
  next_closes_at: string | null;
}

export interface EmailSettings {
  id: number;
  from_email_default: string;
  reply_to_default: string;
  effective_from_email: string;
}

export interface BrandingSettings {
  id: number;
  organization_name: string;
  logo: string | null;
}

export interface VoucherSettings {
  id: number;
  adult_amount: number;
  child_amount: number;
  infant_modifier: number;
  active: boolean;
}

export interface ProgramPause {
  id: number;
  reason: string | null;
  pause_start: string;
  pause_end: string;
  multiplier: number;
  is_active: boolean;
  archived: boolean;
  archived_at: string | null;
  last_resync_at: string | null;
  last_resync_by_username: string | null;
}

export interface PauseFormData {
  id: number | null;
  reason: string;
  pause_start: string;
  pause_end: string;
}

export interface HygieneSettings {
  id: number;
  hygiene_ratio: number;
  enabled: boolean;
}

export interface LowInventoryAlertSettings {
  id: number;
  threshold: number;
  enabled: boolean;
}

export type WindowStatus =
  | 'open'
  | 'closed'
  | 'paused'
  | 'force_open'
  | 'force_closed'
  | 'disabled'
  | 'no_schedule';

export interface WindowCycle {
  meeting_at: string;
  opens_at: string;
  closes_at: string;
}

export interface ActiveOverride {
  id: number;
  force_status: 'open' | 'closed';
  expires_at: string;
  reason: string;
  created_by_username: string | null;
  is_active: boolean;
}

export interface EffectiveConfig {
  hours_before_class: number;
  hours_before_close: number;
  enabled: boolean;
  is_overridden: boolean;
  hours_before_class_source: 'program' | 'global';
  hours_before_close_source: 'program' | 'global';
  enabled_source: 'program' | 'global';
}

export interface ProgramWindowStatus {
  program_id: number;
  program_name: string;
  meeting_day: string;
  meeting_time: string;
  window_status: WindowStatus;
  cycles: WindowCycle[];
  seconds_until_change: number | null;
  active_order_count: number;
  override: ActiveOverride | null;
  config: EffectiveConfig;
}

export interface OrderWindowDashboardData {
  programs: ProgramWindowStatus[];
  global: OrderWindowSettings;
  as_of: string;
}
