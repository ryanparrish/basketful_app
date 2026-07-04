/**
 * Offline Banner Component
 * Shows warning when user is offline
 */
import React from 'react';
import { Alert, Slide, Box } from '@mui/material';
import { WifiOff, CloudSync } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { useNetworkStatus } from '../shared/hooks/useNetworkStatus';

export const OfflineBanner: React.FC = () => {
  const { t } = useTranslation();
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
          {t('offline.youAreOffline')}
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
          {t('offline.backOnline')}
        </Alert>
      </Slide>
    </Box>
  );
};

export default OfflineBanner;
