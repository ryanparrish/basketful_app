import { useState } from 'react';
import { useNotify } from 'react-admin';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControlLabel,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { API_URL } from '../../../../utils/apiUrl';
import { getCsrfToken } from '../../utils';
import type { EffectiveConfig } from '../../types';

export const InlineConfigPanel = ({
  programId,
  config,
  onSaved,
}: {
  programId: number;
  config: EffectiveConfig;
  onSaved: () => void;
}) => {
  const notify = useNotify();
  const [hbc, setHbc] = useState<string>(String(config.hours_before_class));
  const [hbcl, setHbcl] = useState<string>(String(config.hours_before_close));
  const [enabled, setEnabled] = useState<boolean>(config.enabled);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/programs/${programId}/order-window/`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({
          hours_before_class: parseInt(hbc) || null,
          hours_before_close: parseInt(hbcl) || null,
          enabled,
        }),
      });
      if (res.ok) {
        notify('Program window config saved.', { type: 'success' });
        onSaved();
      } else {
        notify('Error saving config.', { type: 'error' });
      }
    } catch {
      notify('Network error.', { type: 'error' });
    }
    setSaving(false);
  };

  const revert = async () => {
    setSaving(true);
    try {
      await fetch(`${API_URL}/api/v1/programs/${programId}/order-window/`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
      notify('Reverted to global defaults.', { type: 'success' });
      onSaved();
    } catch {
      notify('Network error.', { type: 'error' });
    }
    setSaving(false);
  };

  const srcLabel = (src: 'program' | 'global') =>
    src === 'global' ? (
      <Chip
        label="global"
        size="small"
        variant="outlined"
        sx={{ ml: 1, fontSize: '0.65rem', height: 18 }}
      />
    ) : null;

  return (
    <Box sx={{ mt: 1, p: 1.5, borderRadius: 1, bgcolor: 'action.hover' }}>
      <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary' }}>
        Window Config {config.is_overridden ? '(program override)' : '(using global defaults)'}
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, mt: 1, flexWrap: 'wrap', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <TextField
            size="small"
            type="number"
            label="Opens (hrs before)"
            value={hbc}
            onChange={e => setHbc(e.target.value)}
            sx={{ width: 150 }}
            inputProps={{ min: 1, max: 168 }}
          />
          {srcLabel(config.hours_before_class_source)}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <TextField
            size="small"
            type="number"
            label="Closes (hrs before)"
            value={hbcl}
            onChange={e => setHbcl(e.target.value)}
            sx={{ width: 150 }}
            inputProps={{ min: 0, max: 168 }}
          />
          {srcLabel(config.hours_before_close_source)}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <FormControlLabel
            control={
              <Switch
                checked={enabled}
                size="small"
                onChange={e => setEnabled(e.target.checked)}
              />
            }
            label="Enabled"
          />
          {srcLabel(config.enabled_source)}
        </Box>
      </Box>
      <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
        <Button size="small" variant="contained" onClick={save} disabled={saving}>
          {saving ? <CircularProgress size={14} /> : 'Save'}
        </Button>
        {config.is_overridden && (
          <Button size="small" variant="outlined" color="warning" onClick={revert} disabled={saving}>
            Revert to Global
          </Button>
        )}
      </Box>
    </Box>
  );
};
