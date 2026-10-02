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
import type { ProgramSettings } from '../../types';

export const GraceTab = ({
  grace,
  setGrace,
  onSave,
  saving,
}: {
  grace: ProgramSettings;
  setGrace: (v: ProgramSettings) => void;
  onSave: () => void;
  saving: boolean;
}) => {
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <Box sx={{ maxWidth: 560 }}>
      <Alert severity="warning" sx={{ mb: 3 }}>
        <AlertTitle>⚠️ Impact Warning</AlertTitle>
        Changes take effect immediately for every participant currently shopping. This only
        affects the over-budget warning shown while reviewing a cart — it does not change
        whether an over-budget order can actually be submitted.
      </Alert>

      <FormControlLabel
        control={
          <Switch
            checked={grace.grace_enabled}
            onChange={e => setGrace({ ...grace, grace_enabled: e.target.checked })}
          />
        }
        label="Enable Grace Allowance"
        sx={{ mb: 3 }}
      />

      <TextField
        fullWidth
        type="number"
        label="Grace Amount ($)"
        value={grace.grace_amount}
        onChange={e => setGrace({ ...grace, grace_amount: parseFloat(e.target.value) || 0 })}
        inputProps={{ step: 0.01, min: 0, max: 100 }}
        helperText="A cart over budget by this amount or less shows a warning instead of a blocking error."
        sx={{ mb: 2 }}
        disabled={!grace.grace_enabled}
      />

      <TextField
        fullWidth
        multiline
        minRows={2}
        label="Grace Message"
        value={grace.grace_message}
        onChange={e => setGrace({ ...grace, grace_message: e.target.value })}
        helperText="Shown to participants when their cart is over budget but within the grace amount."
        sx={{ mb: 3 }}
        disabled={!grace.grace_enabled}
      />

      <Button variant="contained" onClick={() => setConfirmOpen(true)} disabled={saving}>
        Save Grace Allowance Settings
      </Button>

      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>⚠️ Confirm Grace Allowance Change</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This will take effect <strong>immediately</strong> for every participant.
          </Alert>
          <Box sx={{ mt: 2 }}>
            <Typography variant="body1" gutterBottom>
              <strong>Enabled:</strong> {grace.grace_enabled ? 'Yes' : 'No'}
            </Typography>
            <Typography variant="body1" gutterBottom>
              <strong>Grace Amount:</strong> ${grace.grace_amount.toFixed(2)}
            </Typography>
            <Typography variant="body1">
              <strong>Message:</strong> {grace.grace_message}
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
