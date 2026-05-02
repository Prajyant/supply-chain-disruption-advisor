/**
 * Utility functions for weather display, alert severity colors,
 * and vessel status colors used across map and dashboard components.
 */

/**
 * Returns an emoji and label for a WMO weather interpretation code.
 * @see https://open-meteo.com/en/docs#weathervariables
 */
export function getWeatherIcon(code: number | null): { emoji: string; label: string } {
  if (code === null || code === undefined) {
    return { emoji: '❓', label: 'Unknown' };
  }

  if (code >= 0 && code <= 1) return { emoji: '☀️', label: 'Clear' };
  if (code >= 2 && code <= 3) return { emoji: '⛅', label: 'Cloudy' };
  if (code >= 45 && code <= 48) return { emoji: '🌫️', label: 'Fog' };
  if (code >= 51 && code <= 57) return { emoji: '🌦️', label: 'Drizzle' };
  if (code >= 61 && code <= 67) return { emoji: '🌧️', label: 'Rain' };
  if (code >= 71 && code <= 77) return { emoji: '🌨️', label: 'Snow' };
  if (code >= 80 && code <= 82) return { emoji: '🌧️', label: 'Showers' };
  if (code >= 85 && code <= 86) return { emoji: '🌨️', label: 'Snow Showers' };
  if (code >= 95 && code <= 99) return { emoji: '⛈️', label: 'Thunderstorm' };

  return { emoji: '❓', label: 'Unknown' };
}

/**
 * Returns a hex color for a weather alert severity level.
 */
export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'medium':
      return '#eab308'; // yellow
    case 'high':
      return '#f97316'; // orange
    case 'critical':
      return '#ef4444'; // red
    default:
      return '#64748b'; // slate
  }
}

/**
 * Returns a hex color for a vessel/shipment status, used for route line coloring.
 */
export function getStatusColor(status: string): string {
  if (!status) return '#64748b';
  const normalized = status.toLowerCase();
  if (normalized.includes('underway') || normalized.includes('sailing')) return '#22c55e'; // green
  if (normalized.includes('anchor') || normalized.includes('wait')) return '#eab308';     // yellow
  if (normalized.includes('delay') || normalized.includes('stop')) return '#ef4444';      // red
  if (normalized.includes('port') || normalized.includes('berth')) return '#3b82f6';      // blue
  return '#64748b'; // slate
}
