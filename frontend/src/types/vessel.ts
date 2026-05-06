/**
 * TypeScript interfaces for the vessel tracking system.
 * Maps to backend API response shapes from /vessels/* endpoints.
 */

export interface VesselIdentity {
  imo_number: string;
  mmsi: string;
  name: string;
  vessel_type: string;
  call_sign: string;
  flag: string;
  length: number;
  beam: number;
  draught: number;
  year_built?: number;
  dwt?: number;
  resolved_at?: string;
}

export interface VesselPosition {
  imo_number: string;
  mmsi?: string;
  latitude: number;
  longitude: number;
  speed: number;
  course: number;
  heading: number;
  nav_status: string;
  destination?: string;
  eta?: string;
  timestamp: string;
}

export interface VesselStatus {
  imo_number: string;
  mmsi?: string;
  name: string;
  vessel_type?: string;
  flag?: string;
  latitude: number;
  longitude: number;
  speed: number;
  course: number;
  heading: number;
  nav_status?: string;
  origin_port?: string;
  destination?: string;
  eta?: string;
  last_update: string;
  status: 'active' | 'stale' | 'silent' | 'danger' | 'unknown';
  in_danger_zone: string | null;
  linked_supplier: string | null;
  linked_shipment_id: string | null;
}

export interface VesselTrack {
  imo_number: string;
  positions: VesselPosition[];
  count: number;
}

export interface DangerZone {
  name: string;
  risk_weight: number;
  lat_min: number;
  lat_max: number;
  lon_min: number;
  lon_max: number;
  vessels_inside: string[];
  vessel_count: number;
  color?: string;
}

export interface FleetSummary {
  total: number;
  active: number;
  stale: number;
  silent: number;
  in_danger_zone: number;
}

export interface VesselWatchlistResponse {
  fleet_summary: FleetSummary;
  vessels: VesselStatus[];
}

export interface VesselSearchResult {
  imo_number: string;
  mmsi?: string;
  name: string;
  vessel_type?: string;
  flag?: string;
  length?: number;
  beam?: number;
}

export interface VesselAnomaly {
  type: 'ais_silence' | 'speed_anomaly' | 'danger_zone_entry';
  imo_number: string;
  vessel_name: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  details: string;
  timestamp: string;
  linked_supplier?: string;
  linked_shipment_id?: string;
}

/** WebSocket message types for vessel tracking */
export interface VesselPositionUpdateMessage {
  type: 'vessel_position_update';
  data: {
    imo_number: string;
    name: string;
    latitude: number;
    longitude: number;
    speed: number;
    course: number;
    status: string;
  };
}

export interface VesselAnomalyMessage {
  type: 'vessel_anomaly';
  data: VesselAnomaly;
}
