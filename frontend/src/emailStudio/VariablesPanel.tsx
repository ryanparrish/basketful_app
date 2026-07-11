/**
 * VariablesPanel — the friendly variable picker for the studio's left
 * panel. Lists each variable available to the current email type with a
 * human label, a copyable {{ token }} chip, and a "code mode only"
 * badge for loop variables ({% for %} can't live in visual Text blocks).
 */
import { useState } from 'react';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import {
  Box,
  Chip,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Tooltip,
  Typography,
} from '@mui/material';

export interface EmailVariableInfo {
  token: string;
  label: string;
  description: string;
  sample_value: unknown;
  kind: 'value' | 'list';
}

export const VariablesPanel = ({
  variables,
  onInsert,
}: {
  variables: EmailVariableInfo[];
  /** Optional: insert directly (e.g. into the subject input). */
  onInsert?: (token: string) => void;
}) => {
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const copyToken = async (token: string) => {
    await navigator.clipboard.writeText(`{{ ${token} }}`);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 1500);
  };

  return (
    <Box data-testid="variables-panel">
      <Typography variant="subtitle2" sx={{ px: 2, pt: 2 }}>
        Variables
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ px: 2 }}>
        Copy a token and paste it into any text — it's replaced with the
        real value when the email is sent.
      </Typography>
      <List dense>
        {variables.map(variable => (
          <ListItem
            key={variable.token}
            secondaryAction={
              variable.kind === 'list' ? null : (
                <Tooltip title={copiedToken === variable.token ? 'Copied!' : 'Copy token'}>
                  <IconButton
                    edge="end"
                    size="small"
                    aria-label={`Copy ${variable.label}`}
                    onClick={() =>
                      onInsert ? onInsert(variable.token) : copyToken(variable.token)
                    }
                  >
                    {copiedToken === variable.token ? (
                      <CheckIcon fontSize="small" color="success" />
                    ) : (
                      <ContentCopyIcon fontSize="small" />
                    )}
                  </IconButton>
                </Tooltip>
              )
            }
          >
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {variable.label}
                  {variable.kind === 'list' && (
                    <Chip label="code mode only" size="small" color="warning" variant="outlined" />
                  )}
                </Box>
              }
              secondary={
                <>
                  <Typography component="span" variant="caption" sx={{ fontFamily: 'monospace' }}>
                    {'{{ '}{variable.token}{' }}'}
                  </Typography>
                  {' — '}
                  {variable.description}
                </>
              }
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
};
