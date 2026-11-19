import { useState, useRef } from 'react';
import { useLogin, useNotify } from 'react-admin';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  Button,
  CardActions,
  CircularProgress,
  Divider,
  Link,
  TextField,
  Box,
  Typography,
  Alert,
  Skeleton,
} from '@mui/material';
import ReCAPTCHA from 'react-google-recaptcha';
import { StaffAuthCard } from '../components/auth/StaffAuthCard';
import { useRecaptchaSiteKey } from '../lib/useRecaptchaSiteKey';
import { apiErrorDetails } from '../lib/api/passwordReset';

/** Participants who land here by mistake (#137) need their own sign-in. */
const PARTICIPANT_SIGN_IN_URL = import.meta.env.VITE_PARTICIPANT_APP_URL || '/cart/login';

interface LoginLocationState {
  /** Set by the reset page after a new password is saved. */
  passwordSet?: boolean;
  username?: string;
}

const loginErrorMessage = (error: unknown): string => {
  const { status, code: errorCode } = apiErrorDetails(error);
  if (status === 429) return 'Too many login attempts. Please wait a few minutes before trying again.';
  if (errorCode === 'recaptcha_failed') return 'reCAPTCHA verification failed. Please try again.';
  if (status === 401 || status === 400) {
    return 'Invalid username or password. Please check your credentials and try again.';
  }
  if (status !== null && status >= 500) return 'The server encountered an error. Please try again later.';
  if (!status) return 'Unable to reach the server. Please check your connection and try again.';
  return 'Invalid username or password';
};

const LoginPage = () => {
  const locationState = (useLocation().state ?? {}) as LoginLocationState;
  const [username, setUsername] = useState(locationState.username ?? '');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [recaptchaToken, setRecaptchaToken] = useState<string | null>(null);
  const [recaptchaError, setRecaptchaError] = useState<string | null>(null);
  const { siteKey: recaptchaSiteKey, isLoading: recaptchaLoading } = useRecaptchaSiteKey();
  const recaptchaRef = useRef<ReCAPTCHA>(null);

  const login = useLogin();
  const notify = useNotify();

  const handleRecaptchaError = () => {
    setRecaptchaError('reCAPTCHA failed to load. Please refresh the page.');
    setRecaptchaToken(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!recaptchaToken) {
      notify('Please complete the reCAPTCHA verification', { type: 'error' });
      return;
    }

    setLoading(true);

    try {
      await login({
        username: username.trim(),
        password,
        recaptcha_token: recaptchaToken,
      });
    } catch (error) {
      console.error('Login error:', error);
      // A reCAPTCHA token is single-use
      recaptchaRef.current?.reset();
      setRecaptchaToken(null);
      notify(loginErrorMessage(error), { type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <StaffAuthCard subtitle="Sign in to continue">
      {locationState.passwordSet && (
        <Alert severity="success" sx={{ mb: 1 }}>
          Your password is set. Sign in with your new password.
        </Alert>
      )}

      <form onSubmit={handleSubmit}>
        <Box sx={{ mt: 2 }}>
          <TextField
            autoFocus={!locationState.username}
            fullWidth
            label="Username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={loading}
            required
            margin="normal"
          />
          <TextField
            autoFocus={!!locationState.username}
            fullWidth
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading}
            required
            margin="normal"
          />
        </Box>

        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
          {recaptchaLoading ? (
            <Skeleton variant="rectangular" width={304} height={78} />
          ) : recaptchaError ? (
            <Alert severity="error" sx={{ width: '100%' }}>
              {recaptchaError}
            </Alert>
          ) : recaptchaSiteKey ? (
            <ReCAPTCHA
              ref={recaptchaRef}
              sitekey={recaptchaSiteKey}
              onChange={setRecaptchaToken}
              onExpired={() => setRecaptchaToken(null)}
              onErrored={handleRecaptchaError}
            />
          ) : null}
        </Box>

        <CardActions sx={{ justifyContent: 'center', mt: 3 }}>
          <Button
            variant="contained"
            type="submit"
            color="primary"
            disabled={loading || !recaptchaToken}
            fullWidth
            size="large"
          >
            {loading ? <CircularProgress size={24} /> : 'Sign In'}
          </Button>
        </CardActions>
      </form>

      <Typography variant="body2" align="center" sx={{ mt: 1 }}>
        <Link component={RouterLink} to="/forgot-password">
          Forgot your password?
        </Link>
      </Typography>

      <Divider sx={{ my: 2 }} />

      <Typography variant="body2" align="center" color="text.secondary">
        Shopping with Basketful?{' '}
        <Link href={PARTICIPANT_SIGN_IN_URL}>Participant sign-in</Link>
      </Typography>
    </StaffAuthCard>
  );
};

export default LoginPage;
