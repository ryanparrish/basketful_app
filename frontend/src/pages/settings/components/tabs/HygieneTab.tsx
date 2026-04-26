import { useState } from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import type { HygieneSettings } from '../../types';

export const HygieneTab = ({
  hygiene,
  setHygiene,
  onSave,
  saving,
}: {
  hygiene: HygieneSettings;
  setHygiene: (v: HygieneSettings) => void;
  onSave: () => void;
  saving: boolean;
}) => {
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <Box sx={{ maxWidth: 560 }}>
      <Alert severity="warning" sx={{ mb: 3 }}>
        <AlertTitle>⚠️ Impact Warning</AlertTitle>
        Changes to hygiene settings affect hygiene balance calculations immediately for all
        participants.
      </Alert>

      <Alert severity="info" sx={{ mb: 3 }}>
        <AlertTitle>Common Ratios</AlertTitle>
        <Typography variant="body2">
          • <strong>0.2500</strong> = 1/4 of balance (25%)
          <br />
          • <strong>0.3333</strong> = 1/3 of balance (33.33%, default)
          <br />
          • <strong>0.5000</strong> = 1/2 of balance (50%)
        </Typography>
      </Alert>

      <TextField
        fullWidth
        type="number"
        label="Hygiene Ratio"
        value={hygiene.hygiene_ratio}
        onChange={e => setHygiene({ ...hygiene, hygiene_ratio: parseFloat(e.target.value) || 0 })}
        inputProps={{ step: 0.0001, min: 0, max: 1 }}
        helperText={`Percentage of available balance for hygiene products (${(hygiene.hygiene_ratio * 100).toFixed(2)}%)`}
        sx={{ mb: 2 }}
      />

      <FormControlLabel
        control={
          <Switch
            checked={hygiene.enabled}
            onChange={e => setHygiene({ ...hygiene, enabled: e.target.checked })}
          />
        }
        label="Enable Hygiene Balance Calculation"
        sx={{ mb: 3 }}
      />

      <Button variant="contained" onClick={() => setConfirmOpen(true)} disabled={saving}>
        Save Hygiene Settings
      </Button>

      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>⚠️ Confirm Hygiene Settings Change</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This will affect hygiene balance calculations{' '}
            <strong>immediately</strong> for all participants.
          </Alert>
          <Box sx={{ mt: 2 }}>
            <Typography variant="body1" gutterBottom>
              <strong>New Ratio:</strong> {hygiene.hygiene_ratio} (
              {(hygiene.hygiene_ratio * 100).toFixed(2)}%)
            </Typography>
            <Typography variant="body1">
              <strong>Enabled:</strong> {hygiene.enabled ? 'Yes' : 'No'}
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            disabled={saving}
            onClick={() => {
              setConfirmOpen(false);
              onSave();
            }}
          >
            {saving ? <CircularProgress size={20} /> : 'Confirm Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
