/**
 * Offline Banner Component
 * Shows warning when user is offline
 */
import React from 'react';
import { Alert, Slide, Box } from '@mui/material';
import { WifiOff, CloudSync } from '@mui/icons-material';
import { useNetworkStatus } from '../shared/hooks/useNetworkStatus';

export const OfflineBanner: React.FC = () => {
  const { isOnline, wasOffline } = useNetworkStatus();

  return (
    <Box sx={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 1400 }}>
      {/* Offline Alert */}
      <Slide direction="down" in={!isOnline} mountOnEnter unmountOnExit>
        <Alert
          severity="warning"
          icon={<WifiOff />}
          sx={{
            borderRadius: 0,
            justifyContent: 'center',
          }}
        >
          You are offline. Some features may be unavailable.
        </Alert>
      </Slide>

      {/* Reconnected Alert */}
      <Slide direction="down" in={isOnline && wasOffline} mountOnEnter unmountOnExit>
        <Alert
          severity="success"
          icon={<CloudSync />}
          sx={{
            borderRadius: 0,
            justifyContent: 'center',
          }}
        >
          You're back online! Syncing data...
        </Alert>
      </Slide>
    </Box>
  );
};

export default OfflineBanner;
