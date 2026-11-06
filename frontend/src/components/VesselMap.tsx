import { useEffect } from 'react';
import { MapContainer, Marker, Popup, TileLayer, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useQuery } from '@tanstack/react-query';
import { DangerZoneOverlay } from './DangerZoneOverlay';
import { WeatherOverlay } from './WeatherOverlay';
import { fetchVesselTrack, fetchDangerZones } from '../services/vesselApi';
import { useVesselStore } from '../store/vesselStore';

// Fix for default marker icons in Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const CARTO_API_KEY = import.meta.env.VITE_CARTO_API_KEY || 'cb1_53jw_1_1841ae38c0cc44e00ce619b5';
const CARTO_TILE_URL = `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${CARTO_API_KEY}`;

// Common port coordinates (maritime channel coordinates)
const PORT_COORDINATES: Record<string, [number, number]> = {
  // Asia
  shanghai: [31.2304, 121.4737],
  yantian: [22.5431, 114.0579],
  ningbo: [29.8683, 121.5440],
  qingdao: [36.0671, 120.3826],
  tianjin: [39.0842, 117.2009],
  dalian: [38.9140, 121.6147],
  busan: [35.1796, 129.0756],
  yokohama: [35.4437, 139.6380],
  tokyo: [35.6762, 139.6503],
  kobe: [34.6901, 135.1956],
  osaka: [34.6937, 135.5023],
  kaohsiung: [22.6273, 120.3014],
  singapore: [1.3521, 103.8198],
  hong_kong: [22.3193, 114.1694],
  mumbai: [19.0760, 72.8777],
  mundra: [22.5108, 69.8048],
  nhava_sheva: [18.9492, 72.9417],
  chennai: [13.0827, 80.2707],
  colombo: [6.9271, 79.8612],
  karachi: [24.8607, 67.0011],
  dubai: [25.2048, 55.2708],
  jeddah: [21.5433, 39.1728],
  ras_tanura: [26.6400, 50.1600],
  // Europe - Major
  rotterdam: [51.9225, 4.4792],
  europoort: [51.9500, 4.0300],
  hamburg: [53.5511, 9.9937],
  antwerp: [51.2194, 4.4025],
  bremerhaven: [53.5396, 8.5809],
  felixstowe: [51.9644, 1.3511],
  southampton: [50.9097, -1.4044],
  portsmouth: [50.8198, -1.0880],
  le_havre: [49.4944, 0.1079],
  marseille: [43.2965, 5.3698],
  genoa: [44.4057, 8.9463],
  bastia: [42.6975, 9.4530],
  barcelona: [41.3851, 2.1734],
  valencia: [39.4699, -0.3763],
  palma: [39.5696, 2.6502],
  lisbon: [38.7223, -9.1393],
  piraeus: [37.9435, 23.6481],
  istanbul: [41.0082, 28.9784],
  constanta: [44.1807, 28.6344],
  // Americas - Maritime channel coordinates
  newark: [40.6895, -74.1745],
  new_york: [40.7128, -74.0060],
  los_angeles: [33.7490, -118.2477],
  long_beach: [33.7683, -118.1943],
  oakland: [37.8044, -122.2712],
  seattle: [47.6062, -122.3321],
  vancouver: [49.2827, -123.1207],
  houston: [29.728, -95.003], // Barbours Cut / Houston Ship Channel
  galveston: [29.310, -94.792], // Galveston Harbor Entrance
  miami: [25.7617, -80.1918],
  savannah: [32.0835, -81.0998],
  charleston: [32.7765, -79.9311],
  norfolk: [36.8468, -76.2852],
  panama: [8.9824, -79.5198],
  manzanillo: [19.0536, -104.3122],
  lazaro_cardenas: [17.9596, -102.1970],
  santos: [-23.9633, -46.3333],
};

function getPortCoordinates(location?: string): [number, number] | undefined {
  if (!location) return undefined;
  const loc = location.toLowerCase().trim();

  const keyNoSpaces = loc.replace(/[^a-z]/g, '');
  if (PORT_COORDINATES[keyNoSpaces]) return PORT_COORDINATES[keyNoSpaces];

  const keyUnderscore = loc.replace(/\s+/g, '_').replace(/[^a-z_]/g, '');
  if (PORT_COORDINATES[keyUnderscore]) return PORT_COORDINATES[keyUnderscore];

  const cleaned = loc
    .replace(/^port\s+of\s+/i, '')
    .replace(/\s+port$/i, '')
    .replace(/,.*$/, '')
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^a-z_]/g, '');
  if (PORT_COORDINATES[cleaned]) return PORT_COORDINATES[cleaned];

  const words = loc.split(/[\s,|]+/).filter((w) => w.length > 2);
  for (const word of words) {
    const wordKey = word.replace(/[^a-z]/g, '');
    if (PORT_COORDINATES[wordKey]) return PORT_COORDINATES[wordKey];
  }

  for (const [portKey, coords] of Object.entries(PORT_COORDINATES)) {
    if (keyNoSpaces.includes(portKey) || portKey.includes(keyNoSpaces)) {
      return coords;
    }
  }

  return undefined;
}

// Exactly matches VesselTracking.tsx rotating chevron icon
function createVesselMarkerIcon(status: string = 'active', heading: number = 0) {
  const colors: Record<string, string> = {
    active: '#22c55e',
    underway: '#22c55e',
    stale: '#f59e0b',
    anchored: '#eab308',
    moored: '#f97316',
    silent: '#ef4444',
    danger: '#ef4444',
    delayed: '#ef4444',
    unknown: '#94a3b8',
  };
  const color = colors[status.toLowerCase()] || colors.active;
  const size = 32;
  const strokeColor = '#38bdf8';
  const strokeWidth = 2.5;

  return L.divIcon({
    className: 'custom-vessel-marker',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
    html: `
      <div style="transform: rotate(${heading}deg); width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center; filter: drop-shadow(0 0 8px rgba(56, 189, 248, 0.7));">
        <svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none">
          <polygon points="12,2 20,20 12,16 4,20" fill="${color}" stroke="${strokeColor}" stroke-width="${strokeWidth}"/>
        </svg>
      </div>
    `,
  });
}

function FlyToPosition({ position }: { position: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    if (position && Array.isArray(position) && Number.isFinite(position[0]) && Number.isFinite(position[1])) {
      map.flyTo(position, 8, { duration: 1.2 });
    }
  }, [position, map]);
  return null;
}

interface VesselMapProps {
  vesselName?: string;
  origin?: string;
  destination?: string;
  latitude?: number | null;
  longitude?: number | null;
  status?: string;
  speed?: number;
  progress?: number;
  transportMode?: string;
  imoNumber?: string;
  mmsi?: string;
  heading?: number;
}

export function VesselMap({
  vesselName,
  origin,
  destination,
  latitude,
  longitude,
  status = 'active',
  speed,
  progress,
  imoNumber,
  mmsi: _mmsi,
  heading = 0,
}: VesselMapProps) {
  const { dangerZones, setDangerZones } = useVesselStore();

  useEffect(() => {
    if (!dangerZones || dangerZones.length === 0) {
      fetchDangerZones().then((res) => setDangerZones(res.zones || [])).catch(() => {});
    }
  }, [dangerZones?.length, setDangerZones]);

  // Fetch real historical track if IMO is available
  const trackQuery = useQuery({
    queryKey: ['vessel-track', imoNumber],
    queryFn: () => fetchVesselTrack(imoNumber!, { hours: 48 }),
    enabled: Boolean(imoNumber),
    staleTime: 60_000,
  });

  const originCoords = getPortCoordinates(origin);
  const destCoords = getPortCoordinates(destination);

  if (typeof latitude !== 'number' || typeof longitude !== 'number') {
    return (
      <div className="flex h-72 items-center justify-center rounded-lg border border-slate-800 bg-slate-950/50 text-slate-500">
        <p className="text-sm">Position telemetry not available</p>
      </div>
    );
  }

  const currentLat = latitude;
  const currentLon = longitude;
  const currentHeading = heading;
  const displayStatus = status.toLowerCase();

  const trackPositions: [number, number][] = trackQuery.data?.positions
    ? (trackQuery.data.positions
        .map((p: any) => {
          const lat = typeof p.latitude === 'number' ? p.latitude : p.lat;
          const lon = typeof p.longitude === 'number' ? p.longitude : p.lon;
          if (typeof lat === 'number' && typeof lon === 'number' && Number.isFinite(lat) && Number.isFinite(lon)) {
            return [lat, lon] as [number, number];
          }
          return null;
        })
        .filter((pt: any): pt is [number, number] => pt !== null))
    : [];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-white">Live Vessel Tracking</h3>
          <span className="rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[11px] font-bold text-emerald-400">
            ● LIVE AIS
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          {speed !== undefined && (
            <span className="text-slate-400">
              Speed: <span className="text-cyan-400 font-mono font-medium">{speed.toFixed(1)} kn</span>
            </span>
          )}
          {currentHeading !== undefined && (
            <span className="text-slate-400">
              Heading: <span className="text-cyan-400 font-mono font-medium">{Math.round(currentHeading)}°</span>
            </span>
          )}
          <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 text-xs font-semibold text-emerald-400 uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            {displayStatus}
          </span>
        </div>
      </div>

      <div className="h-72 overflow-hidden rounded-xl border border-slate-800 shadow-2xl relative">
        <MapContainer
          center={[currentLat, currentLon]}
          zoom={8}
          minZoom={2}
          maxZoom={18}
          style={{ height: '100%', width: '100%', background: '#070f1e' }}
          attributionControl={false}
        >
          {/* Real Carto Dark Tiles — Exact match with VesselTracking page */}
          <TileLayer
            url={CARTO_TILE_URL}
            attribution='&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://openstreetmap.org">OSM</a>'
            subdomains="abcd"
            maxZoom={19}
          />

          {/* Critical Maritime Danger Zones Overlay */}
          <DangerZoneOverlay />

          {/* Smooth auto-focus camera */}
          <FlyToPosition position={[currentLat, currentLon]} />

          {/* Historical vessel track polyline */}
          {trackPositions.length >= 2 && (
            <Polyline
              positions={trackPositions}
              pathOptions={{
                color: '#38bdf8',
                weight: 2.5,
                opacity: 0.85,
                dashArray: '6, 6',
              }}
            />
          )}

          {/* Route path connection to ports */}
          {originCoords && Array.isArray(originCoords) && Number.isFinite(originCoords[0]) && Number.isFinite(originCoords[1]) && (
            <Polyline
              positions={[originCoords, [currentLat, currentLon]]}
              pathOptions={{
                color: '#22c55e',
                weight: 2,
                opacity: 0.6,
                dashArray: '4, 4',
              }}
            />
          )}
          {destCoords && Array.isArray(destCoords) && Number.isFinite(destCoords[0]) && Number.isFinite(destCoords[1]) && (
            <Polyline
              positions={[[currentLat, currentLon], destCoords]}
              pathOptions={{
                color: '#38bdf8',
                weight: 2,
                opacity: 0.6,
                dashArray: '4, 4',
              }}
            />
          )}

          {/* Weather overlay for route points */}
          <WeatherOverlay
            points={[
              originCoords,
              [currentLat, currentLon],
              destCoords,
            ].filter((pt): pt is [number, number] => Array.isArray(pt) && Number.isFinite(pt[0]) && Number.isFinite(pt[1]))}
          />

          {/* Live Vessel Chevron Marker */}
          <Marker
            position={[currentLat, currentLon]}
            icon={createVesselMarkerIcon(displayStatus, currentHeading)}
          >
            <Popup>
              <div className="space-y-1.5 p-1 text-xs font-sans text-slate-200">
                <div className="font-bold text-white text-sm">{vesselName || 'Tracked Vessel'}</div>
                {imoNumber && <div className="text-slate-400">IMO: <span className="font-mono text-cyan-300">{imoNumber}</span></div>}
                <div>Status: <span className="font-semibold text-emerald-400">{status}</span></div>
                {speed !== undefined && <div>Speed: <span className="font-mono text-white">{speed} kn</span></div>}
                {currentHeading !== undefined && <div>Heading: <span className="font-mono text-white">{Math.round(currentHeading)}°</span></div>}
                {progress !== undefined && <div>Route Progress: <span className="font-semibold text-white">{progress}%</span></div>}
                <div className="text-slate-500 font-mono text-[11px] pt-1 border-t border-slate-700">
                  {currentLat.toFixed(4)}°N, {Math.abs(currentLon).toFixed(4)}°W
                </div>
              </div>
            </Popup>
          </Marker>

          {/* Origin Port Terminal Marker */}
          {originCoords && (
            <Marker
              position={originCoords}
              icon={L.divIcon({
                className: 'custom-origin-icon',
                html: `
                  <div style="display:flex;align-items:center;gap:4px;">
                    <div style="width:14px;height:14px;background:#3b82f6;border:2px solid white;border-radius:50%;box-shadow:0 0 10px rgba(59,130,246,0.8);"></div>
                    <span style="background:rgba(15,23,42,0.85);color:#93c5fd;font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;border:1px solid #1e3a8a;white-space:nowrap;">
                      ORIGIN: ${origin || 'Port'}
                    </span>
                  </div>
                `,
                iconSize: [120, 24],
                iconAnchor: [7, 12],
              })}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold text-blue-400">Origin Port Terminal</div>
                  <div>{origin}</div>
                </div>
              </Popup>
            </Marker>
          )}

          {/* Destination Port Terminal Marker */}
          {destCoords && (
            <Marker
              position={destCoords}
              icon={L.divIcon({
                className: 'custom-dest-icon',
                html: `
                  <div style="display:flex;align-items:center;gap:4px;">
                    <div style="width:14px;height:14px;background:#ef4444;border:2px solid white;border-radius:50%;box-shadow:0 0 10px rgba(239,68,68,0.8);"></div>
                    <span style="background:rgba(15,23,42,0.85);color:#fca5a5;font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;border:1px solid #7f1d1d;white-space:nowrap;">
                      DEST: ${destination || 'Port'}
                    </span>
                  </div>
                `,
                iconSize: [120, 24],
                iconAnchor: [7, 12],
              })}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold text-rose-400">Destination Port Terminal</div>
                  <div>{destination}</div>
                </div>
              </Popup>
            </Marker>
          )}
        </MapContainer>
      </div>

      {/* Maritime Map Legend matching VesselTracking */}
      <div className="flex flex-wrap items-center gap-4 text-xs bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2">
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-blue-500" />
          <span className="text-slate-300">Origin Terminal</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-rose-500" />
          <span className="text-slate-300">Destination Terminal</span>
        </div>
        <div className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="#22c55e">
            <polygon points="12,2 20,20 12,16 4,20" />
          </svg>
          <span className="text-slate-300">Underway (Active)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="#f59e0b">
            <polygon points="12,2 20,20 12,16 4,20" />
          </svg>
          <span className="text-slate-300">Anchored / Stale</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 bg-sky-400 inline-block border-b border-dashed border-sky-400" />
          <span className="text-slate-300">Track History</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm bg-rose-500/40 border border-rose-500" />
          <span className="text-slate-300">Danger Zone</span>
        </div>
      </div>
    </div>
  );
}
