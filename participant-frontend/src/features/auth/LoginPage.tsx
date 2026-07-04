/**
 * Login Page
 * Customer number based authentication with reCAPTCHA v2
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
  Skeleton,
} from '@mui/material';
import { Visibility, VisibilityOff, Person, Lock, Refresh } from '@mui/icons-material';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import ReCAPTCHA from 'react-google-recaptcha';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../providers/AuthContext';
import { useThemeConfig } from '../../shared/theme/dynamicTheme';
import { MAX_WIDTHS } from '../../shared/constants/layout';
import { apiClient } from '../../shared/api/secureClient';
import { translateDynamic } from '../../i18n';
import { LanguageSwitcher } from '../../components/LanguageSwitcher';

interface LocationState {
  from?: { pathname: string };
}

interface ProgramConfig {
  recaptcha_site_key?: string;
}

/** Form errors are stored as i18n keys so a language switch retranslates them. */
type LoginFormErrorKey =
  | 'login.enterCustomerNumber'
  | 'login.enterPassword'
  | 'login.completeRecaptcha';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { t, i18n } = useTranslation();
  const { login, isAuthenticated, isLoading, error, clearError } = useAuth();
  const { themeConfig } = useThemeConfig();

  const [customerNumber, setCustomerNumber] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<LoginFormErrorKey | null>(null);

  // reCAPTCHA state
  const [recaptchaToken, setRecaptchaToken] = useState<string | null>(null);
  const [recaptchaSiteKey, setRecaptchaSiteKey] = useState<string | null>(null);
  const [recaptchaLoading, setRecaptchaLoading] = useState(true);
  const [recaptchaFailed, setRecaptchaFailed] = useState(false);
  const recaptchaRef = useRef<ReCAPTCHA>(null);
  
  // Session expired check
  const sessionExpired = searchParams.get('session_expired') === 'true';

  const from = (location.state as LocationState)?.from?.pathname || '/products';

  // Fetch reCAPTCHA site key from backend
  useEffect(() => {
    const fetchRecaptchaKey = async () => {
      try {
        setRecaptchaLoading(true);
        setRecaptchaFailed(false);
        
        const response = await apiClient.get<ProgramConfig>('/settings/program-config/current/');
        const siteKey = response.data?.recaptcha_site_key;
        
        if (siteKey && siteKey !== 'test-public-key') {
          setRecaptchaSiteKey(siteKey);
        } else {
          // Use test key in development - this bypasses actual verification
          setRecaptchaSiteKey('6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI');
        }
      } catch (err) {
        console.error('Failed to load reCAPTCHA config:', err);
        // Use test key as fallback
        setRecaptchaSiteKey('6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI');
      } finally {
        setRecaptchaLoading(false);
      }
    };

    fetchRecaptchaKey();
  }, []);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, from]);

  // Clear errors when inputs change
  useEffect(() => {
    if (error) clearError();
    if (formError) setFormError(null);
  }, [customerNumber, password]);

  const handleRecaptchaChange = useCallback((token: string | null) => {
    setRecaptchaToken(token);
  }, []);

  const handleRecaptchaExpired = useCallback(() => {
    setRecaptchaToken(null);
  }, []);

  const handleRecaptchaError = useCallback(() => {
    setRecaptchaFailed(true);
    setRecaptchaToken(null);
  }, []);

  const handleRetryRecaptcha = () => {
    setRecaptchaFailed(false);
    setRecaptchaLoading(true);
    // Force re-render by clearing and resetting the site key
    setRecaptchaSiteKey(null);
    setTimeout(() => {
      setRecaptchaSiteKey('6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI');
      setRecaptchaLoading(false);
    }, 100);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    // Validation
    if (!customerNumber.trim()) {
      setFormError('login.enterCustomerNumber');
      return;
    }
    if (!password.trim()) {
      setFormError('login.enterPassword');
      return;
    }
    if (!recaptchaToken) {
      setFormError('login.completeRecaptcha');
      return;
    }

    try {
      await login({
        customer_number: customerNumber.trim(),
        password: password,
        recaptcha_token: recaptchaToken,
      });
      // Navigation handled by useEffect above
    } catch (err) {
      // Error is already set in auth context
      console.error('Login failed:', err);
      // Reset reCAPTCHA on failure
      recaptchaRef.current?.reset();
      setRecaptchaToken(null);
    }
  };

  const toggleShowPassword = () => {
    setShowPassword(prev => !prev);
  };

  // Check if form is ready for submission
  const isFormReady = !recaptchaLoading && !recaptchaFailed && recaptchaToken;

  // Translate the stored auth error code; fall back to the backend's
  // (server-translated) detail text for codes without a local translation
  const authErrorText = error
    ? i18n.exists(`authErrors.${error.code}`)
      ? translateDynamic(`authErrors.${error.code}`)
      : error.detail || t('authErrors.default')
    : null;

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
      <Card
        sx={{
          width: '100%',
          maxWidth: MAX_WIDTHS.FORM,
          mx: 'auto',
        }}
        elevation={4}
      >
        <CardContent sx={{ p: 4 }}>
          {/* Logo/App Name */}
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            {themeConfig?.logo ? (
              <Box
                component="img"
                src={themeConfig.logo}
                alt={themeConfig.app_name}
                sx={{
                  maxHeight: 80,
                  maxWidth: '100%',
                  mb: 2,
                }}
              />
            ) : (
              <Typography variant="h4" component="h1" color="primary" gutterBottom>
                {themeConfig?.app_name || 'Basketful'}
              </Typography>
            )}
            <Typography variant="body2" color="text.secondary">
              {t('login.subtitle')}
            </Typography>
          </Box>

          {/* Session Expired Warning */}
          {sessionExpired && (
            <Alert severity="warning" sx={{ mb: 3 }}>
              {t('login.sessionExpired')}
            </Alert>
          )}

          {/* Error Messages */}
          {(authErrorText || formError) && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {formError ? t(formError) : authErrorText}
            </Alert>
          )}

          {/* Login Form */}
          <Box component="form" onSubmit={handleSubmit} noValidate>
            <TextField
              fullWidth
              id="customer-number"
              label={t('login.customerNumber')}
              value={customerNumber}
              onChange={(e) => setCustomerNumber(e.target.value)}
              margin="normal"
              autoComplete="username"
              autoFocus
              disabled={isLoading}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Person color="action" />
                  </InputAdornment>
                ),
              }}
              inputProps={{
                inputMode: 'text',
                'aria-label': t('login.customerNumber'),
              }}
            />

            <TextField
              fullWidth
              id="password"
              label={t('login.password')}
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              margin="normal"
              autoComplete="current-password"
              disabled={isLoading}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Lock color="action" />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label={showPassword ? t('login.hidePassword') : t('login.showPassword')}
                      onClick={toggleShowPassword}
                      edge="end"
                      disabled={isLoading}
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            {/* reCAPTCHA */}
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
              {recaptchaLoading ? (
                <Skeleton variant="rectangular" width={304} height={78} />
              ) : recaptchaFailed ? (
                <Alert
                  severity="error"
                  sx={{ width: '100%' }}
                  action={
                    <IconButton
                      aria-label={t('common.retry')}
                      color="inherit"
                      size="small"
                      onClick={handleRetryRecaptcha}
                    >
                      <Refresh />
                    </IconButton>
                  }
                >
                  {t('login.recaptchaLoadFailed')}
                </Alert>
              ) : recaptchaSiteKey ? (
                <ReCAPTCHA
                  ref={recaptchaRef}
                  sitekey={recaptchaSiteKey}
                  onChange={handleRecaptchaChange}
                  onExpired={handleRecaptchaExpired}
                  onErrored={handleRecaptchaError}
                />
              ) : null}
            </Box>

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={isLoading || !isFormReady}
              sx={{ mt: 3, mb: 2, py: 1.5 }}
            >
              {isLoading ? (
                <CircularProgress size={24} color="inherit" />
              ) : (
                t('common.signIn')
              )}
            </Button>
          </Box>

          {/* Help Text */}
          <Typography
            variant="body2"
            color="text.secondary"
            align="center"
            sx={{ mt: 2 }}
          >
            {t('login.needHelp')}
          </Typography>

          {/* Language Switcher */}
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

export default LoginPage;
