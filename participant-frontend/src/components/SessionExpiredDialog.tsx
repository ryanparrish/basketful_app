/**
 * SessionExpiredDialog Component
 * Displays a modal dialog when the user's session has expired
 * Listens for SESSION_EXPIRED_EVENT from the API client
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
} from '@mui/material';
import { Warning as WarningIcon } from '@mui/icons-material';
import { SESSION_EXPIRED_EVENT } from '../shared/api/secureClient';

export const SessionExpiredDialog: React.FC = () => {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const handleSessionExpired = () => {
      setOpen(true);
    };

    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, []);

  const handleSignIn = () => {
    setOpen(false);
    navigate('/login?session_expired=true');
  };

  return (
    <Dialog
      open={open}
      onClose={() => {}} // Prevent closing by clicking outside
      aria-labelledby="session-expired-dialog-title"
      aria-describedby="session-expired-dialog-description"
    >
      <DialogTitle id="session-expired-dialog-title" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <WarningIcon color="warning" />
        Session Expired
      </DialogTitle>
      <DialogContent>
        <DialogContentText id="session-expired-dialog-description">
          Your session has expired. Please sign in again to continue.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleSignIn} variant="contained" color="primary" autoFocus>
          Sign In
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SessionExpiredDialog;
