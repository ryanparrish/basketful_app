/**
 * Change Password Card
 * Lets a signed-in participant choose a new password from the Account page
 */
import React, { useState } from 'react';
import {
  Alert,
  Button,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { changePassword } from '../shared/api/endpoints';

interface FieldErrors {
  current_password?: string[];
  new_password?: string[];
}

export const ChangePasswordCard: React.FC = () => {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [mismatch, setMismatch] = useState(false);

  const mutation = useMutation({
    mutationFn: changePassword,
    onSuccess: () => {
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    },
  });

  // The server explains what's wrong with each field (wrong current
  // password, too short, too common...)
  const response = (mutation.error as unknown as {
    response?: { status?: number; data?: FieldErrors };
  } | null)?.response;
  const fieldErrors: FieldErrors =
    response?.status === 400 ? response.data ?? {} : {};
  const otherError = mutation.isError && !fieldErrors.current_password && !fieldErrors.new_password;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    mutation.mutate({ current_password: currentPassword, new_password: newPassword });
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t('account.changePassword.title')}
        </Typography>
        <Stack component="form" spacing={2} onSubmit={handleSubmit} noValidate>
          {mutation.isSuccess && (
            <Alert severity="success">{t('account.changePassword.success')}</Alert>
          )}
          {otherError && (
            <Alert severity="error">{t('account.changePassword.failed')}</Alert>
          )}
          <TextField
            type="password"
            label={t('account.changePassword.current')}
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            error={!!fieldErrors.current_password}
            helperText={fieldErrors.current_password?.join(' ')}
            required
            fullWidth
          />
          <TextField
            type="password"
            label={t('account.changePassword.new')}
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            error={!!fieldErrors.new_password}
            helperText={fieldErrors.new_password?.join(' ')}
            required
            fullWidth
          />
          <TextField
            type="password"
            label={t('account.changePassword.confirm')}
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            error={mismatch}
            helperText={mismatch ? t('account.changePassword.mismatch') : undefined}
            required
            fullWidth
          />
          <Button
            type="submit"
            variant="contained"
            disabled={
              mutation.isPending || !currentPassword || !newPassword || !confirmPassword
            }
          >
            {mutation.isPending
              ? t('account.changePassword.saving')
              : t('account.changePassword.submit')}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default ChangePasswordCard;
