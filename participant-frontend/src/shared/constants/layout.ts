/**
 * Layout Constants
 * Centralized layout configuration for consistent responsive design
 */

// Desktop sidebar and cart panel widths (in pixels)
export const DESKTOP_SIDEBAR_WIDTH = 240;
export const DESKTOP_CART_WIDTH = 360;

// Responsive Grid Column Widths
// Note: MUI Grid v2 size prop accepts numbers (1-12) or 'auto'
export const GRID_COLUMNS = {
  // Account Page
  ACCOUNT_PROFILE: { xs: 12, lg: 2.4 } as const, // ~20% (2.4 out of 12)
  ACCOUNT_CONTENT: { xs: 12, lg: 'auto' } as const, // flex: 1
  
  // Two-column layouts
  TWO_COL_NARROW: { xs: 12, lg: 3.6 } as const, // ~30% (3.6 out of 12)
  TWO_COL_WIDE: { xs: 12, lg: 'auto' } as const,
  
  // Three-column layouts
  THREE_COL_EQUAL: { xs: 12, md: 4 } as const,
  THREE_COL_SIDEBAR: { xs: 12, lg: 2.4 } as const, // ~20%
  THREE_COL_MAIN: { xs: 12, lg: 6.6 } as const, // ~55%
  THREE_COL_ASIDE: { xs: 12, lg: 3 } as const, // ~25%
} as const;

// Container padding (responsive)
export const CONTAINER_PADDING = {
  xs: 2,
  sm: 3,
  md: 4,
  lg: 6,
} as const;

// Page padding
export const PAGE_PADDING = {
  x: { xs: 2, lg: 4 },
  y: { xs: 3, lg: 3 },
  bottom: { xs: 10, lg: 3 }, // Extra padding on mobile for bottom nav
} as const;

// Max widths for content containers
export const MAX_WIDTHS = {
  FULL: '100%',
  CONTENT: '1400px',
  NARROW: '900px',
  FORM: '600px',
} as const;

// Responsive breakpoints helper
export const useFullWidth = () => ({
  width: '100%',
  maxWidth: '100%',
});
