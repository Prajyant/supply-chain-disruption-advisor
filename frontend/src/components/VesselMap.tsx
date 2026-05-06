import { MapContainer, Marker, Popup, TileLayer, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { RouteLines } from './RouteLines';
import { FitViewport } from './FitViewport';
import { WeatherOverlay } from './WeatherOverlay';

// Fix for default marker icons in Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Common port coordinates
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
  // Europe - Scandinavia & Baltic
  copenhagen: [55.6761, 12.5683],
  malmo: [55.6050, 13.0038],
  gothenburg: [57.7089, 11.9746],
  stockholm: [59.3293, 18.0686],
  helsinki: [60.1699, 24.9384],
  oslo: [59.9139, 10.7522],
  stavanger: [58.9700, 5.7331],
  bergen: [60.3913, 5.3221],
  tromso: [69.6496, 18.9560],
  hammerfest: [70.6634, 23.6821],
  harstad: [68.7984, 16.5412],
  esbjerg: [55.4760, 8.4519],
  odense: [55.4038, 10.4024],
  kiel: [54.3233, 10.1228],
  rostock: [54.0924, 12.0991],
  gdansk: [54.3520, 18.6466],
  klaipeda: [55.7033, 21.1443],
  // Europe - Other
  immingham: [53.6128, -0.2106],
  belfast: [54.5973, -5.9301],
  dublin: [53.3498, -6.2603],
  london: [51.5074, -0.1278],
  tilbury: [51.4607, 0.3544],
  den_helder: [52.9533, 4.7610],
  texel: [53.0600, 4.8000],
  ijmuiden: [52.4600, 4.6000],
  amsterdam: [52.3676, 4.9041],
  utrecht: [52.0907, 5.1214],
  // Americas
  newark: [40.6895, -74.1745],
  new_york: [40.7128, -74.0060],
  los_angeles: [33.7490, -118.2477],
  long_beach: [33.7683, -118.1943],
  oakland: [37.8044, -122.2712],
  seattle: [47.6062, -122.3321],
  vancouver: [49.2827, -123.1207],
  houston: [29.7604, -95.3698],
  galveston: [29.3013, -94.7977],
  miami: [25.7617, -80.1918],
  savannah: [32.0835, -81.0998],
  charleston: [32.7765, -79.9311],
  norfolk: [36.8468, -76.2852],
  panama: [8.9824, -79.5198],
  manzanillo: [19.0536, -104.3122],
  lazaro_cardenas: [17.9596, -102.1970],
  santos: [-23.9633, -46.3333],
  recife: [-8.0476, -34.8770],
  salvador: [-12.9714, -38.5124],
  // Africa
  durban: [-29.8587, 31.0218],
  cape_town: [-33.9249, 18.4241],
  tangier: [35.7595, -5.8340],
  casablanca: [33.5731, -7.5898],
  alexandria: [31.2001, 29.9187],
  lagos: [6.4541, 3.3947],
  // Oceania
  sydney: [-33.8688, 151.2093],
  melbourne: [-37.8136, 144.9631],
  auckland: [-36.8485, 174.7633],
  // Waterways / Regions
  suez_canal: [30.5852, 32.2654],
  pacific_ocean: [28.0, -160.0],
  north_sea: [56.0, 3.0],
  english_channel: [50.5, -1.0],
  baltic_sea: [57.0, 18.0],
  mediterranean: [38.0, 15.0],
  gulf_of_mexico: [25.0, -90.0],
  norwegian_sea: [67.0, 8.0],
  atlantic_coast: [-5.0, -35.0],
  marmara: [40.7, 28.9],
  black_sea: [43.0, 34.0],
  aegean_sea: [38.5, 25.0],
  ligurian_sea: [43.5, 9.0],
  inland_sea: [34.3, 133.5],
  east_china_sea: [30.0, 126.0],
  irish_sea: [53.5, -5.0],
  scheldt: [51.4, 4.0],
  canal: [52.2, 5.0],
  nieuwe_waterweg: [51.95, 4.1],
  thames: [51.5, 0.5],
};

function getPortCoordinates(location?: string): [number, number] | undefined {
  if (!location) return undefined;

  // Normalize: lowercase, trim
  const loc = location.toLowerCase().trim();

  // Try exact match with various key formats
  const keyNoSpaces = loc.replace(/[^a-z]/g, '');
  if (PORT_COORDINATES[keyNoSpaces]) return PORT_COORDINATES[keyNoSpaces];

  const keyUnderscore = loc.replace(/\s+/g, '_').replace(/[^a-z_]/g, '');
  if (PORT_COORDINATES[keyUnderscore]) return PORT_COORDINATES[keyUnderscore];

  // Try without common suffixes/prefixes
  const cleaned = loc
    .replace(/^port\s+of\s+/i, '')
    .replace(/\s+port$/i, '')
    .replace(/,.*$/, '') // Remove country after comma
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^a-z_]/g, '');
  if (PORT_COORDINATES[cleaned]) return PORT_COORDINATES[cleaned];

  // Try each word individually
  const words = loc.split(/[\s,|]+/).filter(w => w.length > 2);
  for (const word of words) {
    const wordKey = word.replace(/[^a-z]/g, '');
    if (PORT_COORDINATES[wordKey]) return PORT_COORDINATES[wordKey];
  }

  // Try partial match against all port keys
  for (const [portKey, coords] of Object.entries(PORT_COORDINATES)) {
    // Check if location contains the port key or vice versa
    if (keyNoSpaces.includes(portKey) || portKey.includes(keyNoSpaces)) {
      return coords;
    }
    // Check underscore version
    if (keyUnderscore.includes(portKey) || portKey.includes(keyUnderscore.replace(/_/g, ''))) {
      return coords;
    }
  }

  return undefined;
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
}

const STATUS_COLORS: Record<string, string> = {
  underway: '#22c55e', // green
  anchored: '#eab308', // yellow/amber
  moored: '#f97316', // orange
  waiting: '#eab308', // yellow
  delayed: '#ef4444', // red
  stopped: '#ef4444', // red
  not_under_command: '#ef4444', // red
  at_port: '#3b82f6', // blue
  default: '#64748b', // slate
};

function getStatusColor(status?: string): string {
  if (!status) return STATUS_COLORS.default;
  const normalized = status.toLowerCase();

  // Green — actively moving
  if (
    normalized.includes('under way') ||
    normalized.includes('underway') ||
    normalized.includes('sailing') ||
    normalized.includes('using engine') ||
    normalized === 'active'
  ) {
    return STATUS_COLORS.underway;
  }

  // Red — problem states
  if (
    normalized.includes('delay') ||
    normalized.includes('not under command') ||
    normalized.includes('aground') ||
    normalized.includes('disabled') ||
    normalized.includes('stopped')
  ) {
    return STATUS_COLORS.delayed;
  }

  // Yellow/Amber — stationary but not a problem
  if (
    normalized.includes('anchor') ||
    normalized.includes('wait') ||
    normalized.includes('restricted')
  ) {
    return STATUS_COLORS.anchored;
  }

  // Orange — moored
  if (normalized.includes('moor') || normalized.includes('berth')) {
    return STATUS_COLORS.moored;
  }

  // Blue — at port
  if (normalized.includes('port')) {
    return STATUS_COLORS.at_port;
  }

  return STATUS_COLORS.default;
}

function createCustomIcon(color: string): L.DivIcon {
  const vesselSvg = `<path d="M12 2L2 22h20L12 2zm0 4l7 14H5l7-14z"/>`;

  return L.divIcon({
    className: 'custom-vessel-icon',
    html: `
      <div style="
        width: 32px;
        height: 32px;
        background: ${color};
        border: 3px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
      ">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
          ${vesselSvg}
        </svg>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
}

export function VesselMap({
  vesselName,
  origin,
  destination,
  latitude,
  longitude,
  status,
  speed,
  progress,
  transportMode: _transportMode = 'sea',
}: VesselMapProps) {
  // Get coordinates from port names
  const originCoords = getPortCoordinates(origin);
  const destCoords = getPortCoordinates(destination);

  // Default coordinates if vessel position is not available
  const vesselLat = latitude ?? 20;
  const vesselLon = longitude ?? 0;

  if (typeof latitude !== 'number') {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-slate-800 bg-slate-950/50 text-slate-500">
        <p className="text-sm">Position not available</p>
      </div>
    );
  }

  const currentLat = vesselLat;
  const currentLon = vesselLon;
  const currentStatus = status;
  const currentSpeed = speed;
  const statusColor = getStatusColor(currentStatus);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-white">Live Vessel Tracking</h3>
        </div>
        {currentStatus && (
          <span
            className="flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium"
            style={{ backgroundColor: `${statusColor}20`, color: statusColor }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: statusColor }}
            />
            {currentStatus.toUpperCase()}
          </span>
        )}
      </div>

      <div className="h-64 overflow-hidden rounded-lg border border-slate-800">
        <MapContainer
          center={[currentLat, currentLon]}
          zoom={5}
          style={{ height: '100%', width: '100%', background: '#0f172a' }}
          attributionControl={false}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />

          {/* Route lines via sub-component */}
          <RouteLines
            origin={originCoords}
            vessel={
              typeof currentLat === 'number' && typeof currentLon === 'number'
                ? [currentLat, currentLon]
                : undefined
            }
            destination={destCoords}
            status={currentStatus}
          />

          {/* Fit viewport to all visible points */}
          <FitViewport
            origin={originCoords}
            vessel={
              typeof currentLat === 'number' && typeof currentLon === 'number'
                ? [currentLat, currentLon]
                : undefined
            }
            destination={destCoords}
          />

          {/* Weather overlay for route: origin, vessel position, and destination */}
          <WeatherOverlay
            points={[
              originCoords,
              typeof currentLat === 'number' && typeof currentLon === 'number'
                ? [currentLat, currentLon] as [number, number]
                : undefined,
              destCoords,
            ].filter(Boolean) as [number, number][]}
          />

          {/* Current position marker */}
          <Marker
            position={[currentLat, currentLon]}
            icon={createCustomIcon(statusColor)}
          >
            <Popup>
              <div className="space-y-1 text-xs">
                <div className="font-semibold">{vesselName || 'Unknown Vessel'}</div>
                {currentStatus && <div>Status: {currentStatus}</div>}
                {currentSpeed && <div>Speed: {currentSpeed} kn</div>}
                {progress !== undefined && <div>Progress: {progress}%</div>}
                <div className="text-slate-500">
                  {currentLat.toFixed(4)}, {currentLon.toFixed(4)}
                </div>
              </div>
            </Popup>
          </Marker>

          {/* Origin marker */}
          {originCoords && (
            <>
              <CircleMarker
                center={originCoords}
                radius={8}
                pathOptions={{
                  color: '#3b82f6',
                  fillColor: '#3b82f6',
                  fillOpacity: 0.3,
                  weight: 2,
                }}
              />
              <Marker
                position={originCoords}
                icon={L.divIcon({
                  className: 'custom-origin-icon',
                  html: `
                    <div style="
                      width: 16px;
                      height: 16px;
                      background: #3b82f6;
                      border: 2px solid white;
                      border-radius: 50%;
                      box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
                    "></div>
                  `,
                  iconSize: [16, 16],
                  iconAnchor: [8, 8],
                })}
              >
                <Popup>
                  <div className="text-xs">
                    <div className="font-semibold">Origin</div>
                    <div>{origin || 'Unknown'}</div>
                  </div>
                </Popup>
              </Marker>
            </>
          )}

          {/* Destination marker */}
          {destCoords && (
            <>
              <CircleMarker
                center={destCoords}
                radius={8}
                pathOptions={{
                  color: '#ef4444',
                  fillColor: '#ef4444',
                  fillOpacity: 0.3,
                  weight: 2,
                }}
              />
              <Marker
                position={destCoords}
                icon={L.divIcon({
                  className: 'custom-dest-icon',
                  html: `
                    <div style="
                      width: 16px;
                      height: 16px;
                      background: #ef4444;
                      border: 2px solid white;
                      border-radius: 50%;
                      box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);
                    "></div>
                  `,
                  iconSize: [16, 16],
                  iconAnchor: [8, 8],
                })}
              >
                <Popup>
                  <div className="text-xs">
                    <div className="font-semibold">Destination</div>
                    <div>{destination || 'Unknown'}</div>
                  </div>
                </Popup>
              </Marker>
            </>
          )}
        </MapContainer>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-blue-500" />
          <span className="text-slate-400">Origin</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-red-500" />
          <span className="text-slate-400">Destination</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-green-500" />
          <span className="text-slate-400">Underway</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-yellow-500" />
          <span className="text-slate-400">Anchored/Waiting</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-2 rounded-full bg-red-500" />
          <span className="text-slate-400">Delayed</span>
        </div>
      </div>
    </div>
  );
}
