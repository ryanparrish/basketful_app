import { useState, useRef, useEffect } from 'react';
import { useLogin, useNotify } from 'react-admin';
import {
  Avatar,
  Button,
  Card,
  CardActions,
  CircularProgress,
  TextField,
  Box,
  Typography,
  Alert,
  Skeleton,
} from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import ReCAPTCHA from 'react-google-recaptcha';
import apiClient from '../lib/api/apiClient';

interface ProgramConfig {
  recaptcha_site_key?: string;
}

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [recaptchaToken, setRecaptchaToken] = useState<string | null>(null);
  const [recaptchaSiteKey, setRecaptchaSiteKey] = useState<string | null>(null);
  const [recaptchaLoading, setRecaptchaLoading] = useState(true);
  const [recaptchaError, setRecaptchaError] = useState<string | null>(null);
  const recaptchaRef = useRef<ReCAPTCHA>(null);

  const login = useLogin();
  const notify = useNotify();

  // Fetch reCAPTCHA site key on mount
  useEffect(() => {
    const fetchRecaptchaKey = async () => {
      try {
        setRecaptchaLoading(true);
        setRecaptchaError(null);

        const response = await apiClient.get<ProgramConfig>('/settings/program-config/current/');
        const siteKey = response.data?.recaptcha_site_key;

        if (siteKey && siteKey !== 'test-public-key') {
          setRecaptchaSiteKey(siteKey);
        } else {
          // Use Google's test key for development
          setRecaptchaSiteKey('6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI');
        }
      } catch (err) {
        console.error('Failed to load reCAPTCHA config:', err);
        // Fallback to test key
        setRecaptchaSiteKey('6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI');
      } finally {
        setRecaptchaLoading(false);
      }
    };

    fetchRecaptchaKey();
  }, []);

  const handleRecaptchaChange = (token: string | null) => {
    setRecaptchaToken(token);
  };

  const handleRecaptchaExpired = () => {
    setRecaptchaToken(null);
  };

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
    } catch (error: any) {
      console.error('Login error:', error);
      
      // Reset reCAPTCHA on failure
      recaptchaRef.current?.reset();
      setRecaptchaToken(null);

      // Handle specific error codes
      const errorCode = error?.response?.data?.code;
      let errorMessage = 'Invalid username or password';

      if (errorCode === 'recaptcha_failed') {
        errorMessage = 'reCAPTCHA verification failed. Please try again.';
      } else if (error?.message) {
        errorMessage = error.message;
      }

      notify(errorMessage, { type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card sx={{ minWidth: 400, maxWidth: 450, p: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 3 }}>
          <Avatar sx={{ bgcolor: 'primary.main', mb: 2 }}>
            <LockIcon />
          </Avatar>
          <Typography component="h1" variant="h5">
            Basketful Admin
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Sign in to continue
          </Typography>
        </Box>

        <form onSubmit={handleSubmit}>
          <Box sx={{ mt: 2 }}>
            <TextField
              autoFocus
              fullWidth
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              required
              margin="normal"
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
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
                onChange={handleRecaptchaChange}
                onExpired={handleRecaptchaExpired}
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
      </Card>
    </Box>
  );
};

export default LoginPage;
