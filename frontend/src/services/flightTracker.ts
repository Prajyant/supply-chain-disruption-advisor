export interface FlightData {
  callsign: string;
  latitude: number;
  longitude: number;
  altitude: number;
  speed: number;
  heading: number;
  status: 'en_route' | 'landed' | 'delayed' | 'cancelled';
  origin?: string;
  destination?: string;
  departureTime?: string;
  arrivalTime?: string;
}

// Mock flight data for demo purposes
const MOCK_FLIGHTS: Record<string, FlightData> = {
  'FX2001': {
    callsign: 'FX2001',
    latitude: 35.0,
    longitude: -95.0,
    altitude: 35000,
    speed: 450,
    heading: 90,
    status: 'en_route',
    origin: 'Shanghai',
    destination: 'Memphis',
    departureTime: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    arrivalTime: new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
  },
  'UA858': {
    callsign: 'UA858',
    latitude: 40.0,
    longitude: -100.0,
    altitude: 38000,
    speed: 520,
    heading: 85,
    status: 'en_route',
    origin: 'Shanghai',
    destination: 'Newark',
    departureTime: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    arrivalTime: new Date(Date.now() + 5 * 60 * 60 * 1000).toISOString(),
  },
};

// Simulate realtime position updates
function simulateFlightMovement(flight: FlightData): FlightData {
  const now = Date.now();
  const departureTime = flight.departureTime ? new Date(flight.departureTime).getTime() : now;
  const arrivalTime = flight.arrivalTime ? new Date(flight.arrivalTime).getTime() : now + 6 * 60 * 60 * 1000;
  const totalDuration = arrivalTime - departureTime;
  const elapsed = now - departureTime;
  const progress = Math.min(Math.max(elapsed / totalDuration, 0), 1);

  // Simple linear interpolation between origin and destination
  // For demo, we'll just move the longitude based on progress
  const baseLongitude = -120; // Starting point (Pacific)
  const endLongitude = -70; // Ending point (East Coast)
  const currentLongitude = baseLongitude + (endLongitude - baseLongitude) * progress;

  return {
    ...flight,
    longitude: currentLongitude,
    status: progress >= 1 ? 'landed' : 'en_route',
  };
}

export async function getFlightByCallsign(callsign: string): Promise<FlightData | null> {
  // Simulate API delay
  await new Promise((resolve) => setTimeout(resolve, 300));

  const normalizedCallsign = callsign.toUpperCase().replace(/\s/g, '');
  const flight = MOCK_FLIGHTS[normalizedCallsign];

  if (!flight) {
    // Generate a mock flight for unknown callsigns
    return {
      callsign: normalizedCallsign,
      latitude: 35 + Math.random() * 10,
      longitude: -100 + Math.random() * 20,
      altitude: 35000 + Math.random() * 5000,
      speed: 450 + Math.random() * 100,
      heading: 45 + Math.random() * 90,
      status: 'en_route',
      departureTime: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      arrivalTime: new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
    };
  }

  return simulateFlightMovement(flight);
}

export function getFlightStatus(status: FlightData['status']): string {
  switch (status) {
    case 'en_route':
      return 'Underway';
    case 'landed':
      return 'Landed';
    case 'delayed':
      return 'Delayed';
    case 'cancelled':
      return 'Cancelled';
    default:
      return 'Unknown';
  }
}
