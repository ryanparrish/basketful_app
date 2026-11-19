/**
 * Staff: ask for a password reset link by username or email. The answer
 * never says whether an account matched.
 */
import { useRef, useState, type FormEvent } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Alert, Box, Button, CircularProgress, Link, Skeleton, TextField, Typography } from '@mui/material';
import ReCAPTCHA from 'react-google-recaptcha';
import { StaffAuthCard } from '../components/auth/StaffAuthCard';
import { requestPasswordReset, apiErrorDetails } from '../lib/api/passwordReset';
import { useRecaptchaSiteKey } from '../lib/useRecaptchaSiteKey';

const messageFor = (error: unknown): string => {
  const { status, code } = apiErrorDetails(error);
  if (status === 429) return 'Too many requests. Please wait a while and try again.';
  if (code === 'recaptcha_failed') return 'reCAPTCHA verification failed. Please try again.';
  if (code === 'identifier_required') return 'Enter your username or email address.';
  return 'Something went wrong. Please try again.';
};

const ForgotPasswordPage = () => {
  const { siteKey, isLoading: siteKeyLoading } = useRecaptchaSiteKey();
  const recaptchaRef = useRef<ReCAPTCHA>(null);
  const [identifier, setIdentifier] = useState('');
  const [recaptchaToken, setRecaptchaToken] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!identifier.trim()) {
      setError('Enter your username or email address.');
      return;
    }
    if (!recaptchaToken) {
      setError('Please complete the reCAPTCHA verification.');
      return;
    }
    setSending(true);
    setError(null);
    try {
      await requestPasswordReset(identifier.trim(), recaptchaToken);
      setSent(true);
    } catch (requestError) {
      setError(messageFor(requestError));
      recaptchaRef.current?.reset();
      setRecaptchaToken(null);
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <StaffAuthCard subtitle="Check your email">
        <Alert severity="success">
          If an account matches, we sent it an email with a link to set a new password. The link
          works for 3 days.
        </Alert>
        <Button component={RouterLink} to="/login" variant="contained" fullWidth size="large" sx={{ mt: 3 }}>
          Back to sign in
        </Button>
      </StaffAuthCard>
    );
  }

  return (
    <StaffAuthCard subtitle="Reset your password">
      <Typography variant="body2" sx={{ mb: 1 }}>
        Enter your username or email address and we&apos;ll email you a link to set a new password.
      </Typography>
      {error && <Alert severity="error" sx={{ my: 1 }}>{error}</Alert>}
      <form onSubmit={handleSubmit} noValidate>
        <TextField
          autoFocus
          fullWidth
          label="Username or email"
          autoComplete="username"
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
          disabled={sending}
          margin="normal"
        />
        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
          {siteKeyLoading ? (
            <Skeleton variant="rectangular" width={304} height={78} />
          ) : siteKey ? (
            <ReCAPTCHA
              ref={recaptchaRef}
              sitekey={siteKey}
              onChange={setRecaptchaToken}
              onExpired={() => setRecaptchaToken(null)}
              onErrored={() => setRecaptchaToken(null)}
            />
          ) : null}
        </Box>
        <Button
          type="submit"
          variant="contained"
          fullWidth
          size="large"
          disabled={sending || !recaptchaToken}
          sx={{ mt: 3 }}
        >
          {sending ? <CircularProgress size={24} /> : 'Send reset link'}
        </Button>
      </form>
      <Typography variant="body2" align="center" sx={{ mt: 2 }}>
        <Link component={RouterLink} to="/login">Back to sign in</Link>
      </Typography>
    </StaffAuthCard>
  );
};

export default ForgotPasswordPage;
