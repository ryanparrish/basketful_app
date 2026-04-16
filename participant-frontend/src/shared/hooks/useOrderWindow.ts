/**
 * useOrderWindow
 *
 * Polls the participant's own program order-window status using the new
 * per-program engine (get_program_window_status on the backend).
 *
 * - Polls every 60 s while the tab is visible (useVisibilityPolling).
 * - Re-schedules immediately after the page regains focus.
 * - Exposes a reactive `secondsLeft` countdown that ticks down in real time.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getMyWindowStatus } from '../api/endpoints';
import type { ParticipantWindowStatus } from '../types/api';

const POLL_INTERVAL_MS = 60_000;
export const ORDER_WINDOW_QUERY_KEY = ['orderWindow'] as const;

export interface UseOrderWindowResult {
  /** Whether the window is open (includes force_open) */
  isOpen: boolean;
  windowStatus: ParticipantWindowStatus['window_status'] | null;
  nextOpensAt: Date | null;
  nextClosesAt: Date | null;
  programName: string | null;
  overrideReason: string | null;
  /** Live countdown in seconds to the next status change */
  secondsLeft: number | null;
  isLoading: boolean;
  /** Force an immediate refetch */
  refresh: () => void;
}

export const useOrderWindow = (): UseOrderWindowResult => {
  const queryClient = useQueryClient();
  const isVisibleRef = useRef(!document.hidden);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ORDER_WINDOW_QUERY_KEY,
    queryFn: getMyWindowStatus,
    staleTime: POLL_INTERVAL_MS,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: true,
  });

  // ---------------------------------------------------------------------------
  // Live countdown — ticks every second between polls
  // ---------------------------------------------------------------------------
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Snapshot the reference time when we last fetched so the countdown
  // doesn't drift when the component re-renders.
  const fetchedAtRef = useRef<number>(Date.now());

  useEffect(() => {
    if (countdownRef.current) clearInterval(countdownRef.current);

    if (data?.seconds_until_change == null) {
      setSecondsLeft(null);
      return;
    }

    fetchedAtRef.current = Date.now();
    const initial = data.seconds_until_change;

    const tick = () => {
      const elapsed = Math.floor((Date.now() - fetchedAtRef.current) / 1000);
      const remaining = Math.max(0, initial - elapsed);
      setSecondsLeft(remaining);
      // When countdown hits zero trigger a refetch to get the new status
      if (remaining === 0) {
        if (countdownRef.current) clearInterval(countdownRef.current);
        refetch();
      }
    };

    tick();
    countdownRef.current = setInterval(tick, 1000);
    return () => { if (countdownRef.current) clearInterval(countdownRef.current); };
  }, [data?.seconds_until_change, data?.window_status, refetch]);

  // ---------------------------------------------------------------------------
  // Visibility-aware polling — stop ticking when tab is hidden
  // ---------------------------------------------------------------------------
  const handleVisibilityChange = useCallback(() => {
    isVisibleRef.current = !document.hidden;
    if (!document.hidden) {
      // Tab became visible — immediately refresh
      refetch();
    }
  }, [refetch]);

  useEffect(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [handleVisibilityChange]);

  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ORDER_WINDOW_QUERY_KEY });
    refetch();
  }, [queryClient, refetch]);

  return {
    isOpen: data?.is_open ?? false,
    windowStatus: data?.window_status ?? null,
    nextOpensAt: data?.next_opens_at ? new Date(data.next_opens_at) : null,
    nextClosesAt: data?.next_closes_at ? new Date(data.next_closes_at) : null,
    programName: data?.program_name ?? null,
    overrideReason: data?.override_reason ?? null,
    secondsLeft,
    isLoading,
    refresh,
  };
};
