import { Box, Button, TextField } from '@mui/material';
import type { BrandingSettings } from '../../types';

export const BrandingTab = ({
  branding,
  setBranding,
  onSave,
  saving,
}: {
  branding: BrandingSettings;
  setBranding: (v: BrandingSettings) => void;
  onSave: () => void;
  saving: boolean;
}) => (
  <Box sx={{ maxWidth: 500 }}>
    <TextField
      fullWidth
      label="Organization Name"
      value={branding.organization_name}
      onChange={e => setBranding({ ...branding, organization_name: e.target.value })}
      helperText="Displayed on printed orders and documents"
      sx={{ mb: 3 }}
    />
    {branding.logo && (
      <Box sx={{ mb: 2 }}>
        <img
          src={branding.logo}
          alt="Organization Logo"
          style={{ maxWidth: 200, maxHeight: 100 }}
        />
      </Box>
    )}
    <Button variant="contained" onClick={onSave} disabled={saving}>
      Save Branding Settings
    </Button>
  </Box>
);
