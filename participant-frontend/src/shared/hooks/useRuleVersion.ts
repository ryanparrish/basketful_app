/**
 * Rule Version Hook
 * Monitors for rule changes and triggers revalidation
 */
import { useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getProgramConfig } from '../api/endpoints';

interface UseRuleVersionOptions {
  /**
   * Callback when rules change
   */
  onRulesChanged?: () => void;
  /**
   * Poll interval in milliseconds
   */
  pollInterval?: number;
  /**
   * Whether to poll (disable when window not focused)
   */
  enabled?: boolean;
}

export const useRuleVersion = ({
  onRulesChanged,
  pollInterval = 60 * 1000, // 1 minute default
  enabled = true,
}: UseRuleVersionOptions = {}) => {
  const queryClient = useQueryClient();
  const lastVersionRef = useRef<number | null>(null);
  const isInitializedRef = useRef(false);

  // Fetch program config with polling
  const { data: programConfig, refetch } = useQuery({
    queryKey: ['programConfig'],
    queryFn: getProgramConfig,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: enabled ? pollInterval : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });

  // Check for version changes
  useEffect(() => {
    if (!programConfig?.rule_version) return;

    const currentVersion = programConfig.rule_version;

    // Skip initial load
    if (!isInitializedRef.current) {
      lastVersionRef.current = currentVersion;
      isInitializedRef.current = true;
      return;
    }

    // Check if version changed
    if (lastVersionRef.current !== null && lastVersionRef.current !== currentVersion) {
      console.log(`Rule version changed from ${lastVersionRef.current} to ${currentVersion}`);
      
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      queryClient.invalidateQueries({ queryKey: ['balances'] });
      
      // Call callback if provided
      onRulesChanged?.();
    }

    lastVersionRef.current = currentVersion;
  }, [programConfig?.rule_version, onRulesChanged, queryClient]);

  // Manual refresh
  const refresh = useCallback(() => {
    refetch();
  }, [refetch]);

  return {
    ruleVersion: programConfig?.rule_version || null,
    orderWindowOpen: programConfig?.order_window_open ?? false,
    orderWindowCloses: programConfig?.order_window_closes || null,
    programConfig,
    refresh,
  };
};

/**
 * Hook to check if order window is open
 */
export const useOrderWindow = () => {
  const { orderWindowOpen, orderWindowCloses, programConfig } = useRuleVersion();

  // Calculate time remaining if window is open
  const getTimeRemaining = useCallback(() => {
    if (!orderWindowOpen || !orderWindowCloses) {
      return null;
    }

    const closes = new Date(orderWindowCloses);
    const now = new Date();
    const diff = closes.getTime() - now.getTime();

    if (diff <= 0) {
      return null;
    }

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    return { hours, minutes, totalMinutes: Math.floor(diff / (1000 * 60)) };
  }, [orderWindowOpen, orderWindowCloses]);

  return {
    isOpen: orderWindowOpen,
    closesAt: orderWindowCloses ? new Date(orderWindowCloses) : null,
    getTimeRemaining,
    gracePeriodMinutes: programConfig?.grace_period_minutes,
    maxItemsPerOrder: programConfig?.max_items_per_order,
  };
};
