/**
 * Dynamic Theme Configuration
 * Fetches theme from backend with 4-hour caching.
 * Brand colors are defined in tokens.ts — this file wires them into MUI.
 */
import { createTheme, type Theme, type ThemeOptions } from '@mui/material/styles';
import { useQuery } from '@tanstack/react-query';
import { getThemeConfig } from '../api/endpoints';
import type { ThemeConfig } from '../types/api';
import { tokens } from './tokens';

// Default theme values — Basketful brand colors used when backend hasn't loaded yet
const defaultTheme: ThemeConfig = {
  primary_color: tokens.brand.greenPrimary,
  secondary_color: tokens.cta.orange,
  logo: null,
  app_name: 'Basketful',
  favicon: null,
  updated_at: new Date().toISOString(),
};

// Create Material-UI theme from backend config
export const createDynamicTheme = (_config: ThemeConfig): Theme => {
  const themeOptions: ThemeOptions = {
    palette: {
      primary: {
        // Always use brand green — design system enforces this regardless of backend config
        main:  tokens.brand.greenPrimary,
        dark:  tokens.brand.greenDark,
        light: tokens.surface.hover,
        contrastText: '#ffffff',
      },
      secondary: {
        // Always use brand orange for CTA — one button per screen
        main:  tokens.cta.orange,
        light: tokens.cta.orangeTint,
        contrastText: '#FFF7EE',
      },
      background: {
        default: tokens.surface.page,
        paper:   tokens.surface.card,
      },
      text: {
        primary:   tokens.text.body,
        secondary: tokens.text.muted,
      },
      divider: tokens.border.default,
    },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      h1: { fontSize: '2rem',   fontWeight: 500, color: tokens.text.heading },
      h2: { fontSize: '1.75rem', fontWeight: 500, color: tokens.text.heading },
      h3: { fontSize: '1.5rem',  fontWeight: 500, color: tokens.text.heading },
      h4: { fontSize: '1.25rem', fontWeight: 500, color: tokens.text.heading },
      h5: { fontSize: '1.1rem',  fontWeight: 500, color: tokens.text.heading },
      h6: { fontSize: '1rem',    fontWeight: 500, color: tokens.text.heading },
    },
    breakpoints: {
      values: {
        xs: 0,
        sm: 600,
        md: 900,
        lg: 1200,
        xl: 1536,
      },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            minHeight: 44,
            textTransform: 'none',
            borderRadius: 8,
          },
          containedSecondary: {
            // Orange CTA — one per screen only (Checkout button)
            backgroundColor: tokens.cta.orange,
            color: '#FFF7EE',
            '&:hover': {
              backgroundColor: tokens.cta.orangeTint,
              color: tokens.brand.greenDark,
            },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            minWidth: 44,
            minHeight: 44,
          },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            minHeight: 48,
            borderRadius: 6,
            '&.Mui-selected': {
              backgroundColor: tokens.surface.hover,
              color: tokens.brand.greenDark,
              fontWeight: 600,
              '&:hover': {
                backgroundColor: tokens.surface.hover,
              },
            },
            '&:hover': {
              backgroundColor: tokens.surface.hover,
            },
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            minHeight: 48,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            border: `1px solid ${tokens.border.default}`,
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiInputBase-root': {
              minHeight: 48,
              backgroundColor: tokens.surface.card,
            },
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: tokens.border.default,
            },
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: tokens.brand.greenPrimary,
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: tokens.border.focus,
            },
          },
        },
      },
      MuiDivider: {
        styleOverrides: {
          root: {
            borderColor: tokens.border.default,
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 20,
          },
        },
      },
      MuiAppBar: {
        styleOverrides: {
          colorPrimary: {
            backgroundColor: tokens.brand.greenPrimary,
          },
        },
      },
    },
  };

  return createTheme(themeOptions);
};

// Hook to fetch and use theme config
export const useThemeConfig = () => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['themeConfig'],
    queryFn: getThemeConfig,
    staleTime: 4 * 60 * 60 * 1000, // 4 hours
    refetchInterval: 4 * 60 * 60 * 1000, // 4 hours
    retry: 3,
    placeholderData: defaultTheme,
  });

  const themeConfig = data || defaultTheme;
  const theme = createDynamicTheme(themeConfig);

  // Update document title
  if (themeConfig.app_name && document.title !== themeConfig.app_name) {
    document.title = themeConfig.app_name;
  }

  // Update theme color meta tag
  const primaryColor = themeConfig?.primary_color || defaultTheme.primary_color;
  const themeColorMeta = document.querySelector('meta[name="theme-color"]');
  if (themeColorMeta) {
    themeColorMeta.setAttribute('content', primaryColor);
  }

  // Update favicon if provided
  if (themeConfig.favicon) {
    const faviconLink = document.querySelector('link[rel="icon"]') as HTMLLinkElement;
    if (faviconLink && faviconLink.href !== themeConfig.favicon) {
      faviconLink.href = themeConfig.favicon;
    }
  }

  return {
    theme,
    themeConfig,
    isLoading,
    error,
  };
};

// Export default theme for initial render
export const defaultMuiTheme = createDynamicTheme(defaultTheme);
