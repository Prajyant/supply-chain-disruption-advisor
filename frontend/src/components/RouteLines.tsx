import { Polyline } from 'react-leaflet';

interface RouteLinesProps {
  origin?: [number, number];
  vessel?: [number, number];
  destination?: [number, number];
  status?: string;
}

export function RouteLines({ origin, vessel, destination, status }: RouteLinesProps) {
  const isDelayed = status?.toLowerCase().includes('delay') || status?.toLowerCase().includes('stop');
  const pathColor = isDelayed ? '#ef4444' : '#3b82f6';

  return (
    <>
      {origin && vessel && (
        <Polyline
          positions={[origin, vessel]}
          pathOptions={{ color: '#64748b', weight: 2, dashArray: '5, 5', opacity: 0.5 }}
        />
      )}
      {vessel && destination && (
        <Polyline
          positions={[vessel, destination]}
          pathOptions={{ color: pathColor, weight: 2, dashArray: '5, 10', opacity: 0.8 }}
        />
      )}
      {origin && destination && !vessel && (
        <Polyline
          positions={[origin, destination]}
          pathOptions={{ color: '#64748b', weight: 2, dashArray: '5, 5', opacity: 0.5 }}
        />
      )}
    </>
  );
}
