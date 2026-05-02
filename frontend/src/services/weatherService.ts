import api from './api';

export interface RouteWeatherPoint {
  location_name: string;
  latitude: number;
  longitude: number;
  temperature_c: number | null;
  wind_speed_kmh: number;
  wind_gusts_kmh: number;
  precipitation_mm: number;
  weather_code: number | null;
  weather_description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

export interface PositionWeatherData {
  weather: {
    temperature_c: number | null;
    wind_speed_kmh: number;
    wind_gusts_kmh: number;
    precipitation_mm: number;
    weather_code: number | null;
    weather_description: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
  } | null;
  marine: {
    wave_height_m: number;
    wind_wave_height_m: number;
    swell_wave_height_m: number;
    ocean_current_velocity_kmh: number;
    wave_period_s: number;
    wave_direction_deg: number | null;
    ocean_current_direction_deg: number | null;
    severity: 'low' | 'medium' | 'high' | 'critical';
  } | null;
  alerts: {
    type: 'weather' | 'marine';
    severity: string;
    message: string;
  }[];
  latitude: number;
  longitude: number;
}

/**
 * Fetches weather data for a list of route points.
 * Returns an empty array if points is empty or on any network error (silent degradation).
 *
 * @param points - Array of [latitude, longitude] pairs
 * @returns Promise resolving to an array of RouteWeatherPoint
 */
export async function getRouteWeather(
  points: [number, number][]
): Promise<RouteWeatherPoint[]> {
  if (points.length === 0) {
    return [];
  }

  try {
    const pointsParam = points.map(([lat, lon]) => `${lat},${lon}`).join(';');
    const response = await api.get<RouteWeatherPoint[]>('/weather/route', {
      params: { points: pointsParam },
    });
    return response.data;
  } catch {
    // Silent degradation per Req 1.6 — weather is non-critical
    return [];
  }
}


/**
 * Fetches current weather + marine conditions for a single position (vessel location).
 * Returns null on any network error (silent degradation).
 */
export async function getPositionWeather(
  lat: number,
  lon: number
): Promise<PositionWeatherData | null> {
  try {
    const response = await api.get<PositionWeatherData>('/weather/position', {
      params: { lat, lon },
    });
    return response.data;
  } catch {
    return null;
  }
}
