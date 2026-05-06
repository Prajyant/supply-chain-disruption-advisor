/**
 * Zustand store for vessel tracking state.
 *
 * Manages:
 * - Tracked vessels list with current positions
 * - Route visibility toggles per vessel
 * - Selected vessel for detail view
 * - Fleet status summary
 * - WebSocket subscription for real-time updates
 */

import { create } from 'zustand';
import type {
  VesselStatus,
  FleetSummary,
  DangerZone,
  VesselTrack,
  VesselAnomaly,
} from '../types/vessel';

interface VesselState {
  // Data
  vessels: VesselStatus[];
  fleetSummary: FleetSummary | null;
  dangerZones: DangerZone[];
  selectedVessel: string | null; // IMO number
  vesselTracks: Record<string, VesselTrack>; // IMO → track data
  visibleRoutes: Set<string>; // IMO numbers with visible routes
  anomalies: VesselAnomaly[];
  timeRange: '24h' | '7d' | '30d';

  // Loading states
  isLoading: boolean;
  error: string | null;

  // Actions
  setVessels: (vessels: VesselStatus[]) => void;
  setFleetSummary: (summary: FleetSummary) => void;
  setDangerZones: (zones: DangerZone[]) => void;
  selectVessel: (imo: string | null) => void;
  toggleRouteVisibility: (imo: string) => void;
  showAllRoutes: () => void;
  hideAllRoutes: () => void;
  setVesselTrack: (imo: string, track: VesselTrack) => void;
  addAnomaly: (anomaly: VesselAnomaly) => void;
  clearAnomalies: () => void;
  setTimeRange: (range: '24h' | '7d' | '30d') => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // WebSocket position update handler
  updateVesselPosition: (imo: string, lat: number, lon: number, speed: number, course: number) => void;
}

export const useVesselStore = create<VesselState>((set, get) => ({
  // Initial state
  vessels: [],
  fleetSummary: null,
  dangerZones: [],
  selectedVessel: null,
  vesselTracks: {},
  visibleRoutes: new Set<string>(),
  anomalies: [],
  timeRange: '24h',
  isLoading: false,
  error: null,

  // Actions
  setVessels: (vessels) => set({ vessels }),

  setFleetSummary: (summary) => set({ fleetSummary: summary }),

  setDangerZones: (zones) => set({ dangerZones: zones }),

  selectVessel: (imo) => set({ selectedVessel: imo }),

  toggleRouteVisibility: (imo) => {
    const current = new Set(get().visibleRoutes);
    if (current.has(imo)) {
      current.delete(imo);
    } else {
      current.add(imo);
    }
    set({ visibleRoutes: current });
  },

  showAllRoutes: () => {
    const allImos = new Set(get().vessels.map((v) => v.imo_number));
    set({ visibleRoutes: allImos });
  },

  hideAllRoutes: () => set({ visibleRoutes: new Set() }),

  setVesselTrack: (imo, track) => {
    set((state) => ({
      vesselTracks: { ...state.vesselTracks, [imo]: track },
    }));
  },

  addAnomaly: (anomaly) => {
    set((state) => ({
      anomalies: [anomaly, ...state.anomalies].slice(0, 50), // Keep last 50
    }));
  },

  clearAnomalies: () => set({ anomalies: [] }),

  setTimeRange: (range) => set({ timeRange: range }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  updateVesselPosition: (imo, lat, lon, speed, course) => {
    set((state) => ({
      vessels: state.vessels.map((v) =>
        v.imo_number === imo
          ? { ...v, latitude: lat, longitude: lon, speed, course }
          : v
      ),
    }));
  },
}));
