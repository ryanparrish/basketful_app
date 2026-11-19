/**
 * Staff: set a new password from an emailed link. The link lands on
 * /reset-password/:uid/:token; the token comes off the address bar at once
 * and is kept for this tab only.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom';
import { Alert, Box, Button, CircularProgress, Stack, TextField, Typography } from '@mui/material';
import { StaffAuthCard } from '../components/auth/StaffAuthCard';
import {
  confirmPasswordReset,
  apiErrorDetails,
  validatePasswordResetLink,
  type PasswordResetLink,
} from '../lib/api/passwordReset';

const STORAGE_KEY = 'basketful_staff_reset_link';

/** Keep the link for this tab, then take it off the address bar. */
const useResetLink = (): PasswordResetLink | null => {
  const { uid, token } = useParams();
  const navigate = useNavigate();
  const [link] = useState<PasswordResetLink | null>(() => {
    try {
      if (uid && token) {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ uid, token }));
        return { uid, token };
      }
      const stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? 'null');
      return stored?.uid && stored?.token ? stored : null;
    } catch {
      return uid && token ? { uid, token } : null;
    }
  });

  useEffect(() => {
    if (uid && token) navigate('/reset-password', { replace: true });
  }, [uid, token, navigate]);

  return link;
};

type LinkState = 'checking' | 'valid' | 'invalid';

const ResetPasswordPage = () => {
  const link = useResetLink();
  const navigate = useNavigate();
  const [linkState, setLinkState] = useState<LinkState>(link ? 'checking' : 'invalid');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [mismatch, setMismatch] = useState(false);
  const [passwordProblems, setPasswordProblems] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!link) return;
    validatePasswordResetLink(link)
      .then(() => setLinkState('valid'))
      .catch(() => setLinkState('invalid'));
  }, [link]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!link) return;
    if (newPassword !== confirmPassword) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    setPasswordProblems(null);
    setFailed(false);
    setSaving(true);
    try {
      const result = await confirmPasswordReset(link, newPassword);
      sessionStorage.removeItem(STORAGE_KEY);
      navigate('/login', { replace: true, state: { passwordSet: true, username: result.sign_in_as } });
    } catch (error) {
      const { code, data } = apiErrorDetails(error);
      if (code === 'invalid_link') setLinkState('invalid');
      else if (code === 'invalid_password' && Array.isArray(data.new_password)) {
        setPasswordProblems((data.new_password as string[]).join(' '));
      } else setFailed(true);
    } finally {
      setSaving(false);
    }
  };

  if (linkState === 'invalid') {
    return (
      <StaffAuthCard subtitle="This link has expired">
        <Alert severity="warning">
          This link is no longer valid. It may have been used already or be more than 3 days old.
        </Alert>
        <Button component={RouterLink} to="/forgot-password" variant="contained" fullWidth size="large" sx={{ mt: 3 }}>
          Get a new link
        </Button>
      </StaffAuthCard>
    );
  }

  if (linkState === 'checking') {
    return (
      <StaffAuthCard subtitle="Checking your link…">
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress />
        </Box>
      </StaffAuthCard>
    );
  }

  return (
    <StaffAuthCard subtitle="Set a new password">
      <Stack component="form" spacing={2} onSubmit={handleSubmit} noValidate>
        <Typography variant="body2">Choose a new password for your account.</Typography>
        {failed && <Alert severity="error">Your password could not be set. Please try again.</Alert>}
        <TextField
          autoFocus
          fullWidth
          type="password"
          label="New password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          error={!!passwordProblems}
          helperText={passwordProblems}
          disabled={saving}
        />
        <TextField
          fullWidth
          type="password"
          label="Confirm new password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          error={mismatch}
          helperText={mismatch ? "The passwords don't match." : undefined}
          disabled={saving}
        />
        <Button
          type="submit"
          variant="contained"
          fullWidth
          size="large"
          disabled={saving || !newPassword || !confirmPassword}
        >
          {saving ? <CircularProgress size={24} /> : 'Set password'}
        </Button>
      </Stack>
    </StaffAuthCard>
  );
};

export default ResetPasswordPage;
