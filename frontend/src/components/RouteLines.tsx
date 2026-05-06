interface RouteLinesProps {
  origin?: [number, number];
  vessel?: [number, number];
  destination?: [number, number];
  status?: string;
}

export function RouteLines(_props: RouteLinesProps) {
  // Route lines removed — we cannot determine exact shipping routes
  return null;
}
