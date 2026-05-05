/**
 * Basketful Design Tokens
 *
 * Single source of truth for all colors used in the participant frontend.
 * Every color in the UI must reference one of these tokens — no one-off hex values in components.
 *
 * Usage:
 *   import { tokens } from '@/shared/theme/tokens';
 *   bgcolor: tokens.surface.page
 *
 * MUI palette mapping:
 *   primary.main        → tokens.brand.greenPrimary
 *   primary.dark        → tokens.brand.greenDark
 *   secondary.main      → tokens.cta.orange       (checkout button only)
 *   background.default  → tokens.surface.page
 *   background.paper    → tokens.surface.card
 *   text.primary        → tokens.text.body
 *   text.secondary      → tokens.text.muted
 *   divider             → tokens.border.default
 */

export const tokens = {
  /** Brand greens — header, links, focus rings, active states */
  brand: {
    greenPrimary: '#2F8A46',
    greenDark:    '#1A3D28',
  },

  /**
   * Call to action — orange appears on ONE element per screen (the primary action button).
   * Never use for badges, icons, decorative elements, or secondary actions.
   */
  cta: {
    orange:     '#E8841A',
    orangeTint: '#FAD8A8',
  },

  /** Surface fills — page bg, cards, hover states */
  surface: {
    page:  '#F4F9F5',
    card:  '#FFFFFF',
    hover: '#E6F2E9',
  },

  /** Text hierarchy */
  text: {
    heading: '#1A3D28',
    body:    '#4A6E52',
    muted:   '#7AA080',
  },

  /** Border colors */
  border: {
    default: '#C8DECE',
    focus:   '#2F8A46',
  },

  /**
   * Semantic status — used for availability badges and alerts.
   * Background tints are rgba values; text colors are accessible on white/tint backgrounds.
   */
  status: {
    available: {
      bg:   'rgba(47, 138, 70, 0.10)',
      text: '#1A5C2A',
    },
    low: {
      bg:   'rgba(232, 132, 26, 0.10)',
      text: '#8A450A',
    },
    full: {
      bg:   'rgba(200, 54, 54, 0.10)',
      text: '#842020',
    },
  },
} as const;

/**
 * CSS custom property names — mirrors tokens above.
 * Injected into :root via index.css.
 * Reference in sx props with: 'var(--color-green-primary)'
 */
export const cssVarNames = {
  greenPrimary:        '--color-green-primary',
  greenDark:           '--color-green-dark',
  orangeCta:           '--color-orange-cta',
  orangeTint:          '--color-orange-tint',
  surfacePage:         '--color-surface-page',
  surfaceCard:         '--color-surface-card',
  surfaceHover:        '--color-surface-hover',
  textHeading:         '--color-text-heading',
  textBody:            '--color-text-body',
  textMuted:           '--color-text-muted',
  borderDefault:       '--color-border-default',
  borderFocus:         '--color-border-focus',
  statusAvailableBg:   '--color-status-available-bg',
  statusAvailableText: '--color-status-available-text',
  statusLowBg:         '--color-status-low-bg',
  statusLowText:       '--color-status-low-text',
  statusFullBg:        '--color-status-full-bg',
  statusFullText:      '--color-status-full-text',
} as const;
