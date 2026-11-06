import api from './api';

export interface IntelligenceEvent {
  id: string;
  source: string;
  title: string;
  summary: string;
  published_at: string | null;
  url: string | null;
  severity: string;
  latitude: number | null;
  longitude: number | null;
  location: string | null;
}

export interface LiveIntelligenceResponse {
  events: IntelligenceEvent[];
  count: number;
  refreshed_at: string;
  cache_ttl_seconds: number;
}

export async function getLiveIntelligence(limit = 12): Promise<LiveIntelligenceResponse> {
  const { data } = await api.get<LiveIntelligenceResponse>('/intelligence/live', {
    params: { limit },
  });
  return data;
}
