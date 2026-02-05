/**
 * Visibility Polling Hook
 * Polls for updates only when page is visible
 */
import { useEffect, useRef, useCallback } from 'react';

interface UseVisibilityPollingOptions {
  /**
   * Callback to execute when polling
   */
  onPoll: () => void | Promise<void>;
  /**
   * Interval in milliseconds
   */
  interval: number;
  /**
   * Whether polling is enabled
   */
  enabled?: boolean;
  /**
   * Whether to poll immediately on mount
   */
  immediate?: boolean;
}

export const useVisibilityPolling = ({
  onPoll,
  interval,
  enabled = true,
  immediate = false,
}: UseVisibilityPollingOptions) => {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const isVisibleRef = useRef(!document.hidden);

  const startPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    if (enabled && isVisibleRef.current) {
      intervalRef.current = setInterval(() => {
        if (isVisibleRef.current) {
          onPoll();
        }
      }, interval);
    }
  }, [onPoll, interval, enabled]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Handle visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      isVisibleRef.current = !document.hidden;
      
      if (document.hidden) {
        stopPolling();
      } else {
        // Poll immediately when becoming visible
        onPoll();
        startPolling();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [onPoll, startPolling, stopPolling]);

  // Start/stop polling based on enabled
  useEffect(() => {
    if (enabled) {
      if (immediate) {
        onPoll();
      }
      startPolling();
    } else {
      stopPolling();
    }

    return () => {
      stopPolling();
    };
  }, [enabled, immediate, onPoll, startPolling, stopPolling]);

  return {
    isPolling: intervalRef.current !== null,
    stopPolling,
    startPolling,
  };
};
