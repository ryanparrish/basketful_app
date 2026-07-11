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
    <TextField
      fullWidth
      label="Participant App URL"
      value={email.participant_frontend_url}
      onChange={e => setEmail({ ...email, participant_frontend_url: e.target.value })}
      helperText="Where email links send participants to shop and log in (e.g. https://shop.example.org). Leave blank to use the server environment setting."
      sx={{ mb: 2 }}
    />
    <TextField
      fullWidth
      label="Backend Domain"
      value={email.backend_domain}
      onChange={e => setEmail({ ...email, backend_domain: e.target.value })}
      helperText="Domain used for password-reset links in emails (e.g. api.example.org). Leave blank to use the server environment setting."
      sx={{ mb: 2 }}
    />
    <Alert severity="info" sx={{ mb: 3 }}>
      Effective From Email: {email.effective_from_email || 'System Default'}
      <br />
      Effective Participant App URL: {email.effective_participant_frontend_url}
      <br />
      Effective Backend Domain: {email.effective_backend_domain}
    </Alert>
    <Button variant="contained" onClick={onSave} disabled={saving}>
      Save Email Settings
    </Button>
  </Box>
);
