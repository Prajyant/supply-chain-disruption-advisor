/**
 * VesselTracking — Dedicated full-page vessel tracking view.
 *
 * Features:
 * - Full-width Leaflet map with all vessel routes and danger zones
 * - Vessel list panel with filters (status, region, linked supplier, vessel type)
 * - Fleet statistics bar (active/stale/silent/danger zone counts)
 * - Time-range selector for route display
 * - "Focus on vessel" button
 */

import { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Ship, RefreshCw, Clock } from 'lucide-react';
import { useVesselStore } from '../store/vesselStore';
import { VesselWatchlist } from '../components/VesselWatchlist';
import { VesselRouteLayer } from '../components/VesselRouteLayer';
import { VesselStatusCard } from '../components/VesselStatusCard';
import { VesselAlertBanner } from '../components/VesselAlertBanner';
import { DangerZoneOverlay } from '../components/DangerZoneOverlay';
import { fetchWatchlist, fetchDangerZones, reloadWatchlist } from '../services/vesselApi';
import type { VesselStatus } from '../types/vessel';

// Vessel marker icon based on status
function createVesselIcon(status: string, heading: number = 0): L.DivIcon {
  const colors: Record<string, string> = {
    active: '#00ff88',
    stale: '#ff8800',
    silent: '#ff3355',
    danger: '#ff3355',
    unknown: '#888888',
  };
  const color = colors[status] || colors.unknown;

  return L.divIcon({
    className: 'vessel-marker',
    html: `<svg width="20" height="20" viewBox="0 0 20 20" style="transform: rotate(${heading}deg)">
      <polygon points="10,2 16,18 10,14 4,18" fill="${color}" stroke="#fff" stroke-width="0.5" opacity="0.9"/>
    </svg>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    popupAnchor: [0, -10],
  });
}

// Component to fly to a vessel
function FlyToVessel({ vessel }: { vessel: VesselStatus | null }) {
  const map = useMap();
  useEffect(() => {
    if (vessel && vessel.latitude && vessel.longitude) {
      map.flyTo([vessel.latitude, vessel.longitude], 8, { duration: 1 });
    }
  }, [vessel, map]);
  return null;
}

export function VesselTracking() {
  const {
    vessels, setVessels, fleetSummary, setFleetSummary,
    dangerZones, setDangerZones, selectedVessel, selectVessel,
    timeRange, setTimeRange, isLoading, setLoading, setError,
  } = useVesselStore();

  const [showPanel, setShowPanel] = useState(true);

  // Load data on mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [watchlistData, zonesData] = await Promise.all([
        fetchWatchlist(),
        fetchDangerZones(),
      ]);
      setVessels(watchlistData.vessels);
      setFleetSummary(watchlistData.fleet_summary);
      setDangerZones(zonesData.zones);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load vessel data');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleReload = async () => {
    setLoading(true);
    try {
      await reloadWatchlist();
      await loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const selectedVesselData = vessels.find((v) => v.imo_number === selectedVessel) || null;

  return (
    <div className="flex h-[calc(100vh-64px)] bg-gray-950">
      {/* Sidebar */}
      {showPanel && (
        <div className="w-72 flex-shrink-0 flex flex-col">
          <VesselWatchlist onVesselSelect={(imo) => selectVessel(imo)} />
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-700">
          {/* Fleet stats */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowPanel(!showPanel)}
              className="p-1 rounded hover:bg-gray-800"
              title="Toggle panel"
            >
              <Ship className="w-4 h-4 text-blue-400" />
            </button>

            {fleetSummary && (
              <div className="flex items-center gap-3 text-xs">
                <span className="text-green-400">🟢 {fleetSummary.active} active</span>
                <span className="text-yellow-400">🟡 {fleetSummary.stale} stale</span>
                <span className="text-red-400">🔴 {fleetSummary.silent} silent</span>
                <span className="text-red-400">⚠ {fleetSummary.in_danger_zone} in danger</span>
                <span className="text-gray-500">| {fleetSummary.total} total</span>
              </div>
            )}
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            {/* Time range selector */}
            <div className="flex items-center gap-1 bg-gray-800 rounded px-1">
              <Clock className="w-3 h-3 text-gray-500" />
              {(['24h', '7d', '30d'] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range)}
                  className={`px-2 py-0.5 text-xs rounded ${
                    timeRange === range
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>

            <button
              onClick={handleReload}
              disabled={isLoading}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-800 text-gray-300 rounded hover:bg-gray-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
              Reload
            </button>
          </div>
        </div>

        {/* Alerts */}
        <VesselAlertBanner />

        {/* Map */}
        <div className="flex-1 relative">
          <MapContainer
            center={[20, 40]}
            zoom={3}
            className="h-full w-full"
            style={{ background: '#0a0a1a' }}
          >
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; OpenStreetMap &copy; CARTO'
            />

            {/* Danger zone overlays */}
            <DangerZoneOverlay />

            {/* Route polylines */}
            <VesselRouteLayer />

            {/* Vessel markers */}
            {vessels
              .filter((v) => v.latitude && v.longitude)
              .map((vessel) => (
                <Marker
                  key={vessel.imo_number}
                  position={[vessel.latitude, vessel.longitude]}
                  icon={createVesselIcon(vessel.status, vessel.heading)}
                  eventHandlers={{
                    click: () => selectVessel(vessel.imo_number),
                  }}
                >
                  <Popup maxWidth={320}>
                    <VesselStatusCard vessel={vessel} />
                  </Popup>
                </Marker>
              ))}

            {/* Fly to selected vessel */}
            <FlyToVessel vessel={selectedVesselData} />
          </MapContainer>

          {/* Selected vessel detail overlay */}
          {selectedVesselData && (
            <div className="absolute top-4 right-4 z-[1000]">
              <VesselStatusCard
                vessel={selectedVesselData}
                onClose={() => selectVessel(null)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
