import { Marker, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import { useQuery } from '@tanstack/react-query';
import { getRouteWeather, type RouteWeatherPoint } from '../services/weatherService';
import { getWeatherIcon, getSeverityColor } from './weatherUtils';

interface WeatherOverlayProps {
  points: [number, number][];
}

export function WeatherOverlay({ points }: WeatherOverlayProps) {
  const { data, isError } = useQuery<RouteWeatherPoint[]>({
    queryKey: ['weather-route', points],
    queryFn: () => getRouteWeather(points),
    staleTime: 5 * 60 * 1000,
    enabled: points.length > 0,
  });

  if (isError || !data || !Array.isArray(data) || data.length === 0) {
    return null;
  }

  return (
    <>
      {data
        .filter((point) => point.severity !== 'low')
        .map((point, index) => {
          const { emoji } = getWeatherIcon(point.weather_code);
          const bgColor = getSeverityColor(point.severity);

          const divIcon = L.divIcon({
            className: '',
            html: `
              <div style="
                width: 32px;
                height: 32px;
                background: ${bgColor};
                border-radius: 50%;
                border: 2px solid white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.4);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
                line-height: 1;
              ">${emoji}</div>
            `,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
          });

          return (
            <Marker
              key={`weather-${index}-${point.latitude}-${point.longitude}`}
              position={[point.latitude, point.longitude]}
              icon={divIcon}
              zIndexOffset={-100}
            >
              <Tooltip>
                <div style={{ fontSize: '12px', lineHeight: '1.6' }}>
                  <div>📍 {point.location_name}</div>
                  <div>🌡️ {point.temperature_c !== null ? `${point.temperature_c}°C` : 'N/A'}</div>
                  <div>💨 {point.wind_speed_kmh} km/h</div>
                  <div>🌧️ {point.precipitation_mm} mm</div>
                  <div>{point.weather_description}</div>
                </div>
              </Tooltip>
            </Marker>
          );
        })}
    </>
  );
}
