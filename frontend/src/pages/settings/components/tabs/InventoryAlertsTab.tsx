import {
  Alert,
  AlertTitle,
  Box,
  Button,
  CircularProgress,
  FormControlLabel,
  Switch,
  TextField,
} from '@mui/material';
import type { LowInventoryAlertSettings } from '../../types';

export const InventoryAlertsTab = ({
  settings,
  setSettings,
  onSave,
  saving,
}: {
  settings: LowInventoryAlertSettings;
  setSettings: (v: LowInventoryAlertSettings) => void;
  onSave: () => void;
  saving: boolean;
}) => (
  <Box sx={{ maxWidth: 560 }}>
    <Alert severity="info" sx={{ mb: 3 }}>
      <AlertTitle>How Low Inventory Alerts Work</AlertTitle>
      When any active product's stock drops to or below the threshold, an email alert is sent to
      all members of the <strong>Inventory Managers</strong> group. Each product alerts once per
      low episode — it must recover above the threshold before it can alert again. Manage
      recipients by editing that group's membership.
    </Alert>

    <TextField
      fullWidth
      type="number"
      label="Low Stock Threshold"
      value={settings.threshold}
      onChange={e => setSettings({ ...settings, threshold: parseInt(e.target.value, 10) || 0 })}
      inputProps={{ min: 0, step: 1 }}
      helperText="Alert when a product's quantity in stock is at or below this value"
      sx={{ mb: 2 }}
    />

    <FormControlLabel
      control={
        <Switch
          checked={settings.enabled}
          onChange={e => setSettings({ ...settings, enabled: e.target.checked })}
        />
      }
      label="Enable Low Inventory Alerts"
      sx={{ mb: 3, display: 'block' }}
    />

    <Button variant="contained" onClick={onSave} disabled={saving}>
      {saving ? <CircularProgress size={20} /> : 'Save Inventory Alert Settings'}
    </Button>
  </Box>
);
