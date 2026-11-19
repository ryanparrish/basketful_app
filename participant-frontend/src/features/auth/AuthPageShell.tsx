/**
 * Auth Page Shell
 * The branded card every signed-out page sits in: sign-in, forgot password,
 * set a new password. Phone-first: full width with a small gutter.
 */
import React from 'react';
import { Box, Card, CardContent, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useThemeConfig } from '../../shared/theme/dynamicTheme';
import { MAX_WIDTHS } from '../../shared/constants/layout';
import { LanguageSwitcher } from '../../components/LanguageSwitcher';

interface AuthPageShellProps {
  /** Line under the logo, e.g. "Sign in to your account". */
  subtitle: string;
  children: React.ReactNode;
}

const ProgramBrand: React.FC = () => {
  const { themeConfig } = useThemeConfig();

  if (themeConfig?.logo) {
    return (
      <Box
        component="img"
        src={themeConfig.logo}
        alt={themeConfig.app_name}
        sx={{ maxHeight: 80, maxWidth: '100%', mb: 2 }}
      />
    );
  }
  return (
    <Typography variant="h4" component="h1" color="primary" gutterBottom>
      {themeConfig?.app_name || 'Basketful'}
    </Typography>
  );
};

export const AuthPageShell: React.FC<AuthPageShellProps> = ({ subtitle, children }) => {
  const { t } = useTranslation();

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        p: 2,
      }}
    >
      <Card sx={{ width: '100%', maxWidth: MAX_WIDTHS.FORM, mx: 'auto' }} elevation={4}>
        <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <ProgramBrand />
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          </Box>

          {children}

          <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 2 }}>
            {t('login.needHelp')}
          </Typography>

          <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
            <Box sx={{ minWidth: 180 }}>
              <LanguageSwitcher variant="select" />
            </Box>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default AuthPageShell;
