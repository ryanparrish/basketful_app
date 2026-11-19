/**
 * Forgot Password Page
 * A participant asks for a reset link by customer number or email. The
 * answer never says whether an account matched.
 */
import React, { useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  InputAdornment,
  Link,
  Skeleton,
  TextField,
  Typography,
} from '@mui/material';
import { Person } from '@mui/icons-material';
import { Link as RouterLink } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import ReCAPTCHA from 'react-google-recaptcha';
import { useTranslation } from 'react-i18next';
import { requestPasswordReset } from '../../shared/api/endpoints';
import { apiErrorDetails } from '../../shared/api/errors';
import { AuthPageShell } from './AuthPageShell';
import { useRecaptchaSiteKey } from './useRecaptchaSiteKey';

type ForgotPasswordErrorKey =
  | 'forgotPassword.enterIdentifier'
  | 'login.completeRecaptcha'
  | 'authErrors.recaptcha_failed'
  | 'forgotPassword.tooMany'
  | 'forgotPassword.failed';

const errorKeyFor = (error: unknown): ForgotPasswordErrorKey => {
  const { status, code } = apiErrorDetails(error);
  if (status === 429) return 'forgotPassword.tooMany';
  if (code === 'recaptcha_failed') return 'authErrors.recaptcha_failed';
  if (code === 'identifier_required') return 'forgotPassword.enterIdentifier';
  return 'forgotPassword.failed';
};

const BackToSignIn: React.FC = () => {
  const { t } = useTranslation();
  return (
    <Typography variant="body2" align="center" sx={{ mt: 2 }}>
      <Link component={RouterLink} to="/login">
        {t('forgotPassword.backToSignIn')}
      </Link>
    </Typography>
  );
};

const ResetLinkSent: React.FC = () => {
  const { t } = useTranslation();
  return (
    <>
      <Alert severity="success" sx={{ mb: 2 }}>
        <Typography variant="subtitle2" component="p" gutterBottom>
          {t('forgotPassword.sentTitle')}
        </Typography>
        {t('forgotPassword.sent')}
      </Alert>
      <Typography variant="body2" color="text.secondary">
        {t('forgotPassword.noEmail')}
      </Typography>
      <Button component={RouterLink} to="/login" fullWidth variant="contained" size="large" sx={{ mt: 3, py: 1.5 }}>
        {t('forgotPassword.backToSignIn')}
      </Button>
    </>
  );
};

export const ForgotPasswordPage: React.FC = () => {
  const { t } = useTranslation();
  const { siteKey, isLoading: siteKeyLoading } = useRecaptchaSiteKey();
  const recaptchaRef = useRef<ReCAPTCHA>(null);

  const [identifier, setIdentifier] = useState('');
  const [recaptchaToken, setRecaptchaToken] = useState<string | null>(null);
  const [formError, setFormError] = useState<ForgotPasswordErrorKey | null>(null);

  const resetRequest = useMutation({
    mutationFn: requestPasswordReset,
    onError: (error) => {
      setFormError(errorKeyFor(error));
      // A reCAPTCHA token is single-use
      recaptchaRef.current?.reset();
      setRecaptchaToken(null);
    },
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!identifier.trim()) {
      setFormError('forgotPassword.enterIdentifier');
      return;
    }
    if (!recaptchaToken) {
      setFormError('login.completeRecaptcha');
      return;
    }
    setFormError(null);
    resetRequest.mutate({ identifier: identifier.trim(), recaptcha_token: recaptchaToken });
  };

  if (resetRequest.isSuccess) {
    return (
      <AuthPageShell subtitle={t('forgotPassword.title')}>
        <ResetLinkSent />
      </AuthPageShell>
    );
  }

  return (
    <AuthPageShell subtitle={t('forgotPassword.title')}>
      <Typography variant="body2" sx={{ mb: 2 }}>
        {t('forgotPassword.instructions')}
      </Typography>

      {formError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {t(formError)}
        </Alert>
      )}

      <Box component="form" onSubmit={handleSubmit} noValidate>
        <TextField
          fullWidth
          id="reset-identifier"
          label={t('forgotPassword.identifier')}
          value={identifier}
          onChange={(e) => {
            setIdentifier(e.target.value);
            setFormError(null);
          }}
          margin="normal"
          autoComplete="username"
          autoCapitalize="characters"
          autoFocus
          disabled={resetRequest.isPending}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Person color="action" />
              </InputAdornment>
            ),
          }}
        />

        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
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
          fullWidth
          variant="contained"
          size="large"
          disabled={resetRequest.isPending || !recaptchaToken}
          sx={{ mt: 3, mb: 1, py: 1.5 }}
        >
          {resetRequest.isPending ? (
            <CircularProgress size={24} color="inherit" />
          ) : (
            t('forgotPassword.submit')
          )}
        </Button>
      </Box>

      <BackToSignIn />
    </AuthPageShell>
  );
};

export default ForgotPasswordPage;
