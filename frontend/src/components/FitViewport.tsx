import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

interface FitViewportProps {
  origin?: [number, number];
  vessel?: [number, number];
  destination?: [number, number];
}

export function FitViewport({ origin, vessel, destination }: FitViewportProps) {
  const map = useMap();

  useEffect(() => {
    const points: [number, number][] = [];
    if (origin) points.push(origin);
    if (vessel) points.push(vessel);
    if (destination) points.push(destination);

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 8 });
    }
  }, [map, origin, vessel, destination]);

  return null;
}
