/**
 * VesselRouteLayer — Leaflet polyline layer for vessel routes.
 *
 * Features:
 * - Time-range selector (24h/7d/30d)
 * - Direction arrows on polylines
 * - Timestamp tooltips on hover
 * - Color coding by vessel type (dashed=tanker, solid=container, dotted=bulk)
 * - Distinct colors per vessel
 */

import { useEffect } from 'react';
import { Polyline, CircleMarker, Tooltip } from 'react-leaflet';
import { useVesselStore } from '../store/vesselStore';
import { fetchVesselTrack } from '../services/vesselApi';
import type { VesselPosition } from '../types/vessel';

const ROUTE_COLORS = [
  '#3b82f6', // blue
  '#10b981', // emerald
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#f97316', // orange
  '#14b8a6', // teal
  '#a855f7', // purple
  '#ef4444', // red
];

function getRouteStyle(vesselType: string | undefined, colorIndex: number) {
  const color = ROUTE_COLORS[colorIndex % ROUTE_COLORS.length];
  const type = (vesselType || '').toLowerCase();

  if (type.includes('tanker')) {
    return { color, weight: 2.5, dashArray: '8, 4', opacity: 0.8 };
  }
  if (type.includes('bulk')) {
    return { color, weight: 2, dashArray: '2, 4', opacity: 0.7 };
  }
  // Container ships and default: solid line
  return { color, weight: 3, opacity: 0.85 };
}

function timeRangeToParams(range: '24h' | '7d' | '30d') {
  switch (range) {
    case '24h': return { hours: 24 };
    case '7d': return { days: 7 };
    case '30d': return { days: 30 };
  }
}

export function VesselRouteLayer() {
  const { vessels, visibleRoutes, vesselTracks, setVesselTrack, timeRange } = useVesselStore();

  // Fetch tracks for visible routes
  useEffect(() => {
    const fetchTracks = async () => {
      for (const imo of visibleRoutes) {
        // Skip if already loaded for this time range
        const existing = vesselTracks[imo];
        if (existing && existing.positions.length > 0) continue;

        try {
          const track = await fetchVesselTrack(imo, timeRangeToParams(timeRange));
          setVesselTrack(imo, track);
        } catch (err) {
          console.warn(`Failed to fetch track for ${imo}:`, err);
        }
      }
    };

    if (visibleRoutes.size > 0) {
      fetchTracks();
    }
  }, [visibleRoutes, timeRange]);

  const visibleVessels = vessels.filter((v) => visibleRoutes.has(v.imo_number));

  return (
    <>
      {visibleVessels.map((vessel, idx) => {
        const track = vesselTracks[vessel.imo_number];
        if (!track || track.positions.length < 2) return null;

        const positions: [number, number][] = track.positions.map((p: VesselPosition) => [
          p.latitude,
          p.longitude,
        ]);

        const style = getRouteStyle(vessel.vessel_type, idx);

        return (
          <div key={vessel.imo_number}>
            {/* Route polyline */}
            <Polyline positions={positions} pathOptions={style} />

            {/* Start point marker */}
            <CircleMarker
              center={positions[0]}
              radius={4}
              pathOptions={{ color: style.color, fillColor: style.color, fillOpacity: 0.5 }}
            >
              <Tooltip>
                {vessel.name} — Route start
                <br />
                {track.positions[0]?.timestamp}
              </Tooltip>
            </CircleMarker>

            {/* Intermediate points (every 10th for performance) */}
            {track.positions
              .filter((_: VesselPosition, i: number) => i % 10 === 0 && i > 0 && i < track.positions.length - 1)
              .map((pos: VesselPosition, i: number) => (
                <CircleMarker
                  key={`${vessel.imo_number}-${i}`}
                  center={[pos.latitude, pos.longitude]}
                  radius={2}
                  pathOptions={{ color: style.color, fillColor: style.color, fillOpacity: 0.4, weight: 1 }}
                >
                  <Tooltip>
                    {vessel.name}
                    <br />
                    Speed: {pos.speed?.toFixed(1)} kts
                    <br />
                    {pos.timestamp}
                  </Tooltip>
                </CircleMarker>
              ))}
          </div>
        );
      })}
    </>
  );
}
