/**
 * Vessel tracking API service.
 * Communicates with backend /vessels/* endpoints.
 */

import axios from 'axios';
import type {
  VesselWatchlistResponse,
  VesselStatus,
  VesselTrack,
  DangerZone,
  FleetSummary,
  VesselSearchResult,
  VesselIdentity,
} from '../types/vessel';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
});

// Add auth token if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function fetchWatchlist(): Promise<VesselWatchlistResponse> {
  const { data } = await api.get('/vessels/watchlist');
  return data;
}

export async function fetchFleetStatus(): Promise<FleetSummary> {
  const { data } = await api.get('/vessels/fleet-status');
  return data;
}

export async function fetchVesselStatus(imo: string): Promise<VesselStatus> {
  const { data } = await api.get(`/vessels/${imo}/status`);
  return data;
}

export async function fetchVesselTrack(
  imo: string,
  params: { hours?: number; days?: number; from?: string; to?: string } = {}
): Promise<VesselTrack> {
  const { data } = await api.get(`/vessels/${imo}/track`, { params });
  return data;
}

export async function resolveVessel(imo: string): Promise<{ source: string; identity: VesselIdentity }> {
  const { data } = await api.get(`/vessels/resolve/${imo}`);
  return data;
}

export async function searchVessels(query: string): Promise<{ results: VesselSearchResult[]; count: number }> {
  const { data } = await api.get('/vessels/search', { params: { q: query } });
  return data;
}

export async function fetchDangerZones(): Promise<{ zones: DangerZone[] }> {
  const { data } = await api.get('/vessels/danger-zones');
  return data;
}

export async function reloadWatchlist(): Promise<{ status: string; vessel_count: number }> {
  const { data } = await api.post('/vessels/watchlist/reload');
  return data;
}

export async function linkVessel(
  imo: string,
  link: { linked_supplier?: string; linked_shipment_id?: string }
): Promise<void> {
  await api.post(`/vessels/${imo}/link`, link);
}
