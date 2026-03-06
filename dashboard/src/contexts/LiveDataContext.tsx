/**
 * AETHER CareOps — Live Data Context
 * ====================================
 * Provides real-time data from the backend API, merged with mock data.
 * Pages can use this context to get live data when available.
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import { fetchResidents, fetchEvents, fetchTimeline, fetchDashboardStats, fetchAnalytics, simulateEvent, type ApiResident, type ApiEvent, type ApiTimelineEntry, type SimulationResponse } from '../services/api';

// ─── Types ────────────────────────────────────────────────────────────

interface LiveDataState {
  residents: ApiResident[];
  events: Record<string, ApiEvent[]>; // keyed by home_id
  timeline: Record<string, ApiTimelineEntry[]>; // keyed by home_id
  isLoading: boolean;
  error: string | null;
  apiConnected: boolean;
  lastUpdated: number | null;
}

interface LiveDataContextValue extends LiveDataState {
  refetch: () => Promise<void>;
  getResidentEvents: (homeId: string) => ApiEvent[];
  getResidentTimeline: (homeId: string) => ApiTimelineEntry[];
  triggerScenario: (scenario: string, residentId?: string) => Promise<SimulationResponse | null>;
}

// ─── Context ──────────────────────────────────────────────────────────

const LiveDataContext = createContext<LiveDataContextValue | undefined>(undefined);

export function LiveDataProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LiveDataState>({
    residents: [],
    events: {},
    timeline: {},
    isLoading: true,
    error: null,
    apiConnected: false,
    lastUpdated: null,
  });

  const fetchIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(async () => {
    try {
      // Fetch residents from API
      const residents = await fetchResidents();

      // Fetch events and timeline for each resident's home
      const homeIds = [...new Set(residents.map((r) => r.home_id))];
      const eventsMap: Record<string, ApiEvent[]> = {};
      const timelineMap: Record<string, ApiTimelineEntry[]> = {};

      await Promise.all(
        homeIds.map(async (homeId) => {
          try {
            const [events, timeline] = await Promise.all([
              fetchEvents(homeId, 30),
              fetchTimeline(homeId, 14),
            ]);
            eventsMap[homeId] = events;
            timelineMap[homeId] = timeline;
          } catch {
            eventsMap[homeId] = [];
            timelineMap[homeId] = [];
          }
        }),
      );

      setState({
        residents,
        events: eventsMap,
        timeline: timelineMap,
        isLoading: false,
        error: null,
        apiConnected: true,
        lastUpdated: Date.now(),
      });
    } catch (err) {
      console.warn('API unreachable, using mock data:', err);
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Unknown error',
        apiConnected: false,
      }));
    }
  }, []);

  // Initial load + polling every 30s
  useEffect(() => {
    loadData();
    fetchIntervalRef.current = setInterval(loadData, 30000);
    return () => {
      if (fetchIntervalRef.current) clearInterval(fetchIntervalRef.current);
    };
  }, [loadData]);

  const getResidentEvents = useCallback(
    (homeId: string) => state.events[homeId] || [],
    [state.events],
  );

  const getResidentTimeline = useCallback(
    (homeId: string) => state.timeline[homeId] || [],
    [state.timeline],
  );

  const triggerScenario = useCallback(
    async (scenario: string, residentId?: string) => {
      try {
        const result = await simulateEvent({
          scenario: scenario as any,
          resident_id: residentId,
        });
        // Reload after trigger
        setTimeout(loadData, 1000);
        return result;
      } catch (err) {
        console.error('Scenario trigger error:', err);
        return null;
      }
    },
    [loadData],
  );

  const value: LiveDataContextValue = {
    ...state,
    refetch: loadData,
    getResidentEvents,
    getResidentTimeline,
    triggerScenario,
  };

  return <LiveDataContext.Provider value={value}>{children}</LiveDataContext.Provider>;
}

export function useLiveData(): LiveDataContextValue {
  const ctx = useContext(LiveDataContext);
  if (!ctx) {
    throw new Error('useLiveData must be used within a LiveDataProvider');
  }
  return ctx;
}
