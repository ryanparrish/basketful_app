/**
 * Dynamic Theme Configuration
 * Fetches theme from backend with 4-hour caching
 */
import { createTheme, Theme, ThemeOptions } from '@mui/material/styles';
import { useQuery } from '@tanstack/react-query';
import { getThemeConfig } from '../api/endpoints';
import type { ThemeConfig } from '../types/api';

// Default theme values (used before backend theme loads)
const defaultTheme: ThemeConfig = {
  primary_color: '#1976d2',
  secondary_color: '#dc004e',
  logo: null,
  app_name: 'Basketful',
  favicon: null,
  updated_at: new Date().toISOString(),
};

// Create Material-UI theme from backend config
export const createDynamicTheme = (config: ThemeConfig): Theme => {
  const themeOptions: ThemeOptions = {
    palette: {
      primary: {
        main: config.primary_color,
      },
      secondary: {
        main: config.secondary_color,
      },
      background: {
        default: '#f5f5f5',
        paper: '#ffffff',
      },
    },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      h1: {
        fontSize: '2rem',
        fontWeight: 500,
      },
      h2: {
        fontSize: '1.75rem',
        fontWeight: 500,
      },
      h3: {
        fontSize: '1.5rem',
        fontWeight: 500,
      },
      h4: {
        fontSize: '1.25rem',
        fontWeight: 500,
      },
      h5: {
        fontSize: '1.1rem',
        fontWeight: 500,
      },
      h6: {
        fontSize: '1rem',
        fontWeight: 500,
      },
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
            minHeight: 44, // Touch target minimum
            textTransform: 'none',
            borderRadius: 8,
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
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiInputBase-root': {
              minHeight: 48,
            },
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
  const themeColorMeta = document.querySelector('meta[name="theme-color"]');
  if (themeColorMeta) {
    themeColorMeta.setAttribute('content', themeConfig.primary_color);
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
