import { Alert, Box, Button, TextField } from '@mui/material';
import type { EmailSettings } from '../../types';

export const EmailTab = ({
  email,
  setEmail,
  onSave,
  saving,
}: {
  email: EmailSettings;
  setEmail: (v: EmailSettings) => void;
  onSave: () => void;
  saving: boolean;
}) => (
  <Box sx={{ maxWidth: 500 }}>
    <TextField
      fullWidth
      label="Default From Email"
      value={email.from_email_default}
      onChange={e => setEmail({ ...email, from_email_default: e.target.value })}
      helperText="Leave blank to use system default"
      sx={{ mb: 2 }}
    />
    <TextField
      fullWidth
      label="Reply-To Email"
      value={email.reply_to_default}
      onChange={e => setEmail({ ...email, reply_to_default: e.target.value })}
      sx={{ mb: 2 }}
    />
    <Alert severity="info" sx={{ mb: 3 }}>
      Effective From Email: {email.effective_from_email || 'System Default'}
    </Alert>
    <Button variant="contained" onClick={onSave} disabled={saving}>
      Save Email Settings
    </Button>
  </Box>
);
