/**
 * VesselTracking — Real-time Global Vessel & Maritime Supply Chain Monitoring.
 *
 * Built with rock-solid Leaflet mapping:
 * - Real-time dark maritime Carto tiles
 * - Live rotating vessel markers colored by status (active: green, stale: amber, danger/silent: red)
 * - 7 Maritime choke point danger zones overlay
 * - Historical route tracking polylines (24h/7d/30d)
 * - Dynamic sidebar to search, add, track, and untrack vessels in real-time (no CSV required)
 * - Live intelligence & maritime weather overlay
 * - Real-time WebSocket streaming for instant coordinate updates
 */

import { useEffect, useState, useCallback, Component, type ReactNode } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Ship, RefreshCw, Clock, AlertTriangle } from 'lucide-react';
import { useVesselStore } from '../store/vesselStore';
import { VesselWatchlist } from '../components/VesselWatchlist';
import { VesselStatusCard } from '../components/VesselStatusCard';
import { VesselAlertBanner } from '../components/VesselAlertBanner';
import { VesselRouteLayer } from '../components/VesselRouteLayer';
import { DangerZoneOverlay } from '../components/DangerZoneOverlay';
import { LiveIntelligencePanel } from '../components/LiveIntelligencePanel';
import { fetchWatchlist, fetchDangerZones, refreshFleet } from '../services/vesselApi';
import type { VesselStatus } from '../types/vessel';

const CARTO_API_KEY = import.meta.env.VITE_CARTO_API_KEY || 'cb1_53jw_1_1841ae38c0cc44e00ce619b5';
const CARTO_TILE_URL = `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${CARTO_API_KEY}`;

// Helper to create rotating vessel marker icons
function createVesselMarkerIcon(status: string, heading: number = 0, isSelected: boolean = false) {
  const colors: Record<string, string> = {
    active: '#22c55e',
    stale: '#f59e0b',
    silent: '#ef4444',
    danger: '#ef4444',
    unknown: '#94a3b8',
  };
  const color = colors[status] || colors.unknown;
  const size = isSelected ? 32 : 24;
  const strokeColor = isSelected ? '#38bdf8' : '#ffffff';
  const strokeWidth = isSelected ? 2.5 : 1.2;

  return L.divIcon({
    className: 'custom-vessel-marker',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
    html: `
      <div style="transform: rotate(${heading}deg); width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center; filter: drop-shadow(0 0 ${isSelected ? '8px #38bdf8' : '3px rgba(0,0,0,0.8)'});">
        <svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none">
          <polygon points="12,2 20,20 12,16 4,20" fill="${color}" stroke="${strokeColor}" stroke-width="${strokeWidth}"/>
        </svg>
      </div>
    `,
  });
}

// Component to fly to a vessel smoothly
function FlyToVessel({ vessel }: { vessel: VesselStatus | null }) {
  const map = useMap();
  useEffect(() => {
    if (
      vessel &&
      Number.isFinite(vessel.latitude) &&
      Number.isFinite(vessel.longitude) &&
      (vessel.latitude !== 0 || vessel.longitude !== 0)
    ) {
      map.flyTo([vessel.latitude, vessel.longitude], 7, { duration: 1.2 });
    }
  }, [vessel, map]);
  return null;
}

// Error Boundary to prevent any blank screen
export class VesselTrackingErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  state = { hasError: false, error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: any) {
    console.error('VesselTracking error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-[calc(100vh-64px)] w-full flex-col items-center justify-center bg-slate-950 p-6 text-center">
          <div className="max-w-md rounded-2xl border border-red-500/30 bg-slate-900 p-8 shadow-2xl">
            <AlertTriangle className="mx-auto h-12 w-12 text-red-400 mb-4 animate-bounce" />
            <h2 className="text-lg font-bold text-white mb-2">Vessel Tracking Recovery</h2>
            <p className="text-xs text-slate-400 mb-6">
              A temporary error occurred while rendering the vessel map. Click below to reload.
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs rounded-xl transition shadow-lg"
            >
              Reload Tracking Center
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export function VesselTracking() {
  const {
    vessels, setVessels, fleetSummary, setFleetSummary,
    dangerZones: _dangerZones, setDangerZones, selectedVessel, selectVessel,
    timeRange, setTimeRange, isLoading, setLoading, setError, updateVesselPosition,
  } = useVesselStore();

  const [showPanel, setShowPanel] = useState(true);
  const [isLiveSource, setIsLiveSource] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [watchlistData, zonesData] = await Promise.all([
        fetchWatchlist(),
        fetchDangerZones(),
      ]);
      setVessels(watchlistData.vessels || []);
      setFleetSummary(watchlistData.fleet_summary);
      setDangerZones(zonesData.zones || []);
      setIsLiveSource(watchlistData.is_live ?? true);
      setError(null);
    } catch (err: any) {
      console.warn('Failed to load vessel data:', err);
      setError(err.message || 'Failed to load vessel data');
    } finally {
      setLoading(false);
    }
  }, [setVessels, setFleetSummary, setDangerZones, setError, setLoading]);

  // Initial load + 60s background safety poll
  useEffect(() => {
    void loadData();
    const interval = window.setInterval(() => void loadData(), 60_000);
    return () => window.clearInterval(interval);
  }, [loadData]);

  // Real-time WebSocket position updates
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || window.location.origin;
    const websocketUrl = new URL('/ws/all', apiUrl.replace(/^http/, 'ws'));
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const connect = () => {
      try {
        socket = new WebSocket(websocketUrl);
        socket.onmessage = (message) => {
          try {
            const payload = JSON.parse(message.data) as { type?: string; data?: Record<string, unknown> };
            if (payload.type === 'vessel_position_update' && payload.data) {
              const { imo_number, mmsi, latitude, longitude, speed, course } = payload.data;
              const id = String(imo_number || mmsi || '');
              if (
                id &&
                typeof latitude === 'number' &&
                typeof longitude === 'number' &&
                typeof speed === 'number' &&
                typeof course === 'number'
              ) {
                updateVesselPosition(id, latitude, longitude, speed, course);
              }
            }
          } catch {}
        };
        socket.onclose = () => {
          reconnectTimer = window.setTimeout(connect, 10_000);
        };
      } catch {}
    };

    connect();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, [updateVesselPosition]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await refreshFleet();
      await loadData();
    } catch (err: any) {
      console.warn('Refresh failed:', err);
      await loadData();
    } finally {
      setLoading(false);
    }
  };

  const selectedVesselData = vessels.find(
    (v) => v.imo_number === selectedVessel || v.mmsi === selectedVessel
  ) || null;

  return (
    <VesselTrackingErrorBoundary>
      <div className="flex h-[calc(100vh-64px)] bg-gray-950 overflow-hidden font-sans">
        {/* Sidebar */}
        {showPanel && (
          <div className="w-80 flex-shrink-0 flex flex-col z-20 shadow-2xl">
            <VesselWatchlist
              onVesselSelect={(imo) => selectVessel(imo)}
              onRefreshNeeded={loadData}
            />
          </div>
        )}

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col relative">
          {/* Top Control Bar */}
          <div className="flex items-center justify-between px-4 py-2.5 bg-gray-900 border-b border-gray-800 z-10">
            {/* Fleet stats */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowPanel(!showPanel)}
                className={`p-1.5 rounded-lg border transition ${
                  showPanel
                    ? 'bg-blue-600/20 border-blue-500/40 text-blue-400'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white'
                }`}
                title="Toggle Fleet Watchlist Panel"
              >
                <Ship className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-2">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide flex items-center gap-1.5 ${
                    isLiveSource
                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                      : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${isLiveSource ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
                  {isLiveSource ? 'LIVE AIS STREAM' : 'DEMO AIS'}
                </span>
              </div>

              {fleetSummary && (
                <div className="hidden md:flex items-center gap-3 text-xs">
                  <span className="text-emerald-400 font-medium">● {fleetSummary.active} Active</span>
                  <span className="text-amber-400 font-medium">● {fleetSummary.stale} Stale</span>
                  <span className="text-rose-400 font-medium">● {fleetSummary.silent} Silent</span>
                  <span className="text-rose-400 font-medium">⚠ {fleetSummary.in_danger_zone} In Danger</span>
                  <span className="text-slate-500 font-mono">| {fleetSummary.total} Total</span>
                </div>
              )}
            </div>

            {/* Controls */}
            <div className="flex items-center gap-2.5">
              {/* Time Range Selector */}
              <div className="flex items-center gap-1 bg-gray-800 border border-gray-700 rounded-lg px-1.5 py-0.5">
                <Clock className="w-3 h-3 text-gray-500" />
                {(['24h', '7d', '30d'] as const).map((range) => (
                  <button
                    key={range}
                    onClick={() => setTimeRange(range)}
                    className={`px-2 py-0.5 text-xs rounded font-medium transition ${
                      timeRange === range
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {range}
                  </button>
                ))}
              </div>

              {/* Refresh Button */}
              <button
                onClick={handleRefresh}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition disabled:opacity-50 shadow"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
                <span>Live Poll</span>
              </button>
            </div>
          </div>

          {/* Anomaly Alerts Banner */}
          <VesselAlertBanner />

          {/* Interactive Maritime Map */}
          <div className="flex-1 relative overflow-hidden bg-slate-950">
            <MapContainer
              center={[22, 35]}
              zoom={3}
              minZoom={2}
              maxZoom={18}
              className="h-full w-full"
              style={{ background: '#070f1e' }}
            >
              {/* Dark Maritime Carto Tiles with Authorized API Key */}
              <TileLayer
                url={CARTO_TILE_URL}
                attribution='&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://openstreetmap.org">OSM</a>'
                subdomains="abcd"
                maxZoom={19}
              />

              {/* 7 Critical Maritime Danger Zones */}
              <DangerZoneOverlay />

              {/* Historical Polyline Tracks */}
              <VesselRouteLayer />

              {/* Live Vessel Markers */}
              {vessels
                .filter(
                  (v) =>
                    Number.isFinite(v.latitude) &&
                    Number.isFinite(v.longitude) &&
                    (v.latitude !== 0 || v.longitude !== 0)
                )
                .map((vessel, index) => {
                  const id = vessel.imo_number || vessel.mmsi || `vessel-${index}`;
                  const isSelected = selectedVessel === vessel.imo_number || selectedVessel === vessel.mmsi;
                  const heading = vessel.heading || vessel.course || 0;

                  return (
                    <Marker
                      key={id}
                      position={[vessel.latitude, vessel.longitude]}
                      icon={createVesselMarkerIcon(vessel.status, heading, isSelected)}
                      eventHandlers={{
                        click: () => selectVessel(id),
                      }}
                    >
                      <Popup maxWidth={320} className="custom-vessel-popup">
                        <VesselStatusCard vessel={vessel} />
                      </Popup>
                    </Marker>
                  );
                })}

              {/* Focus map camera when selecting a vessel */}
              <FlyToVessel vessel={selectedVesselData} />
            </MapContainer>

            {/* Selected vessel detail overlay */}
            {selectedVesselData && (
              <div className="absolute top-4 right-4 z-[1000] max-w-sm">
                <VesselStatusCard
                  vessel={selectedVesselData}
                  onClose={() => selectVessel(null)}
                />
              </div>
            )}

            {/* Live Intelligence Panel in bottom right */}
            <div className="absolute bottom-4 right-4 z-[1000] hidden xl:block">
              <LiveIntelligencePanel vessel={selectedVesselData} />
            </div>
          </div>
        </div>
      </div>
    </VesselTrackingErrorBoundary>
  );
}

export default VesselTracking;
