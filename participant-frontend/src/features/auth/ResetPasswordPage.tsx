/**
 * Set a New Password
 *
 * The emailed link lands on /reset/:uid/:token (ResetLinkLanding), which
 * tucks the link away, switches to the participant's language and moves to
 * /reset-password (ResetPasswordPage). Finishing goes to sign-in with the
 * customer number filled in.
 */
import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Lock, Visibility, VisibilityOff } from '@mui/icons-material';
import { Link as RouterLink, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  confirmPasswordReset,
  validatePasswordResetLink,
  type PasswordResetLink,
} from '../../shared/api/endpoints';
import { apiErrorDetails } from '../../shared/api/errors';
import { SUPPORTED_LANGUAGE_CODES } from '../../i18n/languages';
import { AuthPageShell } from './AuthPageShell';
import { clearResetLink, readResetLink, storeResetLink } from './resetLink';

/** /reset/:uid/:token — the address the emailed link redirects to. */
export const ResetLinkLanding: React.FC = () => {
  const { uid, token } = useParams();
  const [searchParams] = useSearchParams();
  const { i18n } = useTranslation();

  const language = searchParams.get('lang');
  useEffect(() => {
    if (language && SUPPORTED_LANGUAGE_CODES.includes(language)) {
      void i18n.changeLanguage(language);
    }
  }, [language, i18n]);

  if (uid && token) storeResetLink({ uid, token });
  return <Navigate to="/reset-password" replace />;
};

const ExpiredLink: React.FC = () => {
  const { t } = useTranslation();
  return (
    <>
      <Alert severity="warning" sx={{ mb: 3 }}>
        <Typography variant="subtitle2" component="p" gutterBottom>
          {t('resetPassword.invalidTitle')}
        </Typography>
        {t('resetPassword.invalid')}
      </Alert>
      <Button component={RouterLink} to="/forgot-password" fullWidth variant="contained" size="large" sx={{ py: 1.5 }}>
        {t('resetPassword.requestNew')}
      </Button>
    </>
  );
};

interface PasswordFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  visible: boolean;
  onToggleVisible: () => void;
  error?: string;
  disabled: boolean;
  autoFocus?: boolean;
}

const PasswordField: React.FC<PasswordFieldProps> = ({
  id, label, value, onChange, visible, onToggleVisible, error, disabled, autoFocus,
}) => {
  const { t } = useTranslation();
  return (
    <TextField
      fullWidth
      id={id}
      label={label}
      type={visible ? 'text' : 'password'}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      autoComplete="new-password"
      autoFocus={autoFocus}
      disabled={disabled}
      error={!!error}
      helperText={error}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <Lock color="action" />
          </InputAdornment>
        ),
        endAdornment: (
          <InputAdornment position="end">
            <IconButton
              aria-label={visible ? t('login.hidePassword') : t('login.showPassword')}
              onClick={onToggleVisible}
              edge="end"
              disabled={disabled}
            >
              {visible ? <VisibilityOff /> : <Visibility />}
            </IconButton>
          </InputAdornment>
        ),
      }}
    />
  );
};

const NewPasswordForm: React.FC<{ link: PasswordResetLink; onExpired: () => void }> = ({
  link, onExpired,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [mismatch, setMismatch] = useState(false);

  const setPassword = useMutation({
    mutationFn: confirmPasswordReset,
    onSuccess: (result) => {
      clearResetLink();
      navigate('/login?reset=success', { replace: true, state: { signInAs: result.sign_in_as } });
    },
    onError: (error) => {
      if (apiErrorDetails(error).code === 'invalid_link') onExpired();
    },
  });

  // The server says what's wrong with the password (too short, too common…)
  const { code, data } = apiErrorDetails(setPassword.error);
  const passwordProblems =
    code === 'invalid_password' && Array.isArray(data.new_password)
      ? (data.new_password as string[]).join(' ')
      : undefined;
  const otherError = setPassword.isError && code !== 'invalid_password';

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    setPassword.mutate({ ...link, new_password: newPassword });
  };

  return (
    <Stack component="form" spacing={2} onSubmit={handleSubmit} noValidate>
      <Typography variant="body2">{t('resetPassword.instructions')}</Typography>
      {otherError && <Alert severity="error">{t('resetPassword.failed')}</Alert>}
      <PasswordField
        id="new-password"
        label={t('resetPassword.new')}
        value={newPassword}
        onChange={setNewPassword}
        visible={visible}
        onToggleVisible={() => setVisible((shown) => !shown)}
        error={passwordProblems}
        disabled={setPassword.isPending}
        autoFocus
      />
      <PasswordField
        id="confirm-password"
        label={t('resetPassword.confirm')}
        value={confirmPassword}
        onChange={setConfirmPassword}
        visible={visible}
        onToggleVisible={() => setVisible((shown) => !shown)}
        error={mismatch ? t('resetPassword.mismatch') : undefined}
        disabled={setPassword.isPending}
      />
      <Button
        type="submit"
        fullWidth
        variant="contained"
        size="large"
        disabled={setPassword.isPending || !newPassword || !confirmPassword}
        sx={{ py: 1.5 }}
      >
        {setPassword.isPending ? t('resetPassword.saving') : t('resetPassword.submit')}
      </Button>
    </Stack>
  );
};

/** /reset-password */
export const ResetPasswordPage: React.FC = () => {
  const { t } = useTranslation();
  const [link] = useState(readResetLink);
  const [expired, setExpired] = useState(false);

  const linkCheck = useQuery({
    queryKey: ['password-reset-link', link?.uid, link?.token],
    queryFn: () => validatePasswordResetLink(link as PasswordResetLink),
    enabled: !!link,
    retry: false,
    staleTime: Infinity,
  });

  const linkIsBad = !link || expired || linkCheck.isError;

  return (
    <AuthPageShell subtitle={t('resetPassword.title')}>
      {linkIsBad ? (
        <ExpiredLink />
      ) : linkCheck.isPending ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, py: 3 }}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary">
            {t('resetPassword.checking')}
          </Typography>
        </Box>
      ) : (
        <NewPasswordForm link={link} onExpired={() => setExpired(true)} />
      )}
    </AuthPageShell>
  );
};

export default ResetPasswordPage;
