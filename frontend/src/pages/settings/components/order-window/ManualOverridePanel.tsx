import { useState } from 'react';
import { useNotify } from 'react-admin';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material';
import { API_URL } from '../../../../utils/apiUrl';
import { getCsrfToken, fmt } from '../../utils';
import type { ActiveOverride } from '../../types';

const DURATION_PRESETS = [
  { label: '1 hour', minutes: 60 },
  { label: '2 hours', minutes: 120 },
  { label: '4 hours', minutes: 240 },
  { label: 'End of today', minutes: -1 },
];

export const ManualOverridePanel = ({
  programId,
  programName,
  override,
  onSaved,
}: {
  programId: number;
  programName: string;
  override: ActiveOverride | null;
  onSaved: () => void;
}) => {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const [forceStatus, setForceStatus] = useState<'open' | 'closed'>('closed');
  const [expiresAt, setExpiresAt] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!expiresAt) {
      notify('Expiry time is required.', { type: 'error' });
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/programs/${programId}/order-window/override/`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          body: JSON.stringify({ force_status: forceStatus, expires_at: expiresAt, reason }),
        },
      );
      if (res.ok) {
        notify(`Override applied — window force-${forceStatus}.`, { type: 'success' });
        setOpen(false);
        setReason('');
        onSaved();
      } else {
        const d = await res.json();
        notify(d.detail || 'Error applying override.', { type: 'error' });
      }
    } catch {
      notify('Network error.', { type: 'error' });
    }
    setSaving(false);
  };

  const clearOverride = async () => {
    try {
      await fetch(`${API_URL}/api/v1/programs/${programId}/order-window/override/`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
      notify('Override cleared.', { type: 'success' });
      onSaved();
    } catch {
      notify('Network error.', { type: 'error' });
    }
  };

  const setPreset = (minutes: number) => {
    const d = new Date();
    if (minutes === -1) {
      d.setHours(23, 59, 0, 0);
    } else {
      d.setMinutes(d.getMinutes() + minutes);
    }
    setExpiresAt(d.toISOString().slice(0, 16));
  };

  if (override) {
    return (
      <Box
        sx={{
          mt: 1,
          p: 1.5,
          borderRadius: 1,
          bgcolor: 'warning.lighter',
          border: '1px solid',
          borderColor: 'warning.main',
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 600 }}>
          ⚠️ Override active — force {override.force_status} until {fmt(override.expires_at)}
          {override.created_by_username && ` · set by ${override.created_by_username}`}
        </Typography>
        {override.reason && (
          <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
            {override.reason}
          </Typography>
        )}
        <Button
          size="small"
          variant="outlined"
          color="warning"
          sx={{ mt: 1 }}
          onClick={clearOverride}
        >
          Clear Override
        </Button>
      </Box>
    );
  }

  return (
    <>
      <Button size="small" variant="outlined" sx={{ mt: 1 }} onClick={() => setOpen(true)}>
        Manual Override
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Override: {programName}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', gap: 1, mb: 2, mt: 1 }}>
            {(['closed', 'open'] as const).map(s => (
              <Button
                key={s}
                variant={forceStatus === s ? 'contained' : 'outlined'}
                color={s === 'open' ? 'success' : 'error'}
                onClick={() => setForceStatus(s)}
                fullWidth
              >
                Force {s === 'open' ? '🔓 Open' : '🔒 Closed'}
              </Button>
            ))}
          </Box>
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>
            Quick expiry:
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 2 }}>
            {DURATION_PRESETS.map(p => (
              <Chip
                key={p.label}
                label={p.label}
                size="small"
                onClick={() => setPreset(p.minutes)}
                clickable
              />
            ))}
          </Box>
          <TextField
            fullWidth
            size="small"
            label="Expires at"
            type="datetime-local"
            value={expiresAt}
            onChange={e => setExpiresAt(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            size="small"
            label="Reason (optional)"
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="e.g. inventory audit"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={submit} disabled={saving}>
            {saving ? <CircularProgress size={16} /> : 'Apply Override'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};
