/**
 * Network Status Hook
 * Monitors online/offline status with event listeners
 */
import { useState, useEffect, useCallback } from 'react';

interface NetworkStatus {
  isOnline: boolean;
  wasOffline: boolean;
  lastOnlineAt: Date | null;
  lastOfflineAt: Date | null;
}

export const useNetworkStatus = () => {
  const [status, setStatus] = useState<NetworkStatus>({
    isOnline: navigator.onLine,
    wasOffline: false,
    lastOnlineAt: navigator.onLine ? new Date() : null,
    lastOfflineAt: !navigator.onLine ? new Date() : null,
  });

  useEffect(() => {
    const handleOnline = () => {
      setStatus(prev => ({
        isOnline: true,
        wasOffline: !prev.isOnline ? true : prev.wasOffline,
        lastOnlineAt: new Date(),
        lastOfflineAt: prev.lastOfflineAt,
      }));
    };

    const handleOffline = () => {
      setStatus(prev => ({
        isOnline: false,
        wasOffline: true,
        lastOnlineAt: prev.lastOnlineAt,
        lastOfflineAt: new Date(),
      }));
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const resetWasOffline = useCallback(() => {
    setStatus(prev => ({ ...prev, wasOffline: false }));
  }, []);

  return {
    ...status,
    resetWasOffline,
  };
};

export default useNetworkStatus;
