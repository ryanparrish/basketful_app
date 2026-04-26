import { Alert, Box, Button, TextField } from '@mui/material';
import type { VoucherSettings } from '../../types';

export const VoucherTab = ({
  voucher,
  setVoucher,
  onSave,
  saving,
}: {
  voucher: VoucherSettings | null;
  setVoucher: (v: VoucherSettings) => void;
  onSave: () => void;
  saving: boolean;
}) => {
  if (!voucher) {
    return (
      <Alert severity="warning">
        No active voucher settings found. Create one in the Voucher Settings resource.
      </Alert>
    );
  }

  return (
    <Box sx={{ maxWidth: 500 }}>
      <TextField
        fullWidth
        type="number"
        label="Adult Amount ($)"
        value={voucher.adult_amount}
        onChange={e => setVoucher({ ...voucher, adult_amount: parseFloat(e.target.value) || 0 })}
        inputProps={{ step: 0.5 }}
        sx={{ mb: 2 }}
      />
      <TextField
        fullWidth
        type="number"
        label="Child Amount ($)"
        value={voucher.child_amount}
        onChange={e => setVoucher({ ...voucher, child_amount: parseFloat(e.target.value) || 0 })}
        inputProps={{ step: 0.5 }}
        sx={{ mb: 2 }}
      />
      <TextField
        fullWidth
        type="number"
        label="Infant Modifier ($)"
        value={voucher.infant_modifier}
        onChange={e =>
          setVoucher({ ...voucher, infant_modifier: parseFloat(e.target.value) || 0 })
        }
        inputProps={{ step: 0.5 }}
        helperText="Additional amount added for infants"
        sx={{ mb: 3 }}
      />
      <Button variant="contained" onClick={onSave} disabled={saving}>
        Save Voucher Settings
      </Button>
    </Box>
  );
};
