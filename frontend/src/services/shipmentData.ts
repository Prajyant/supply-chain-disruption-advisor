import { ShipmentInput } from '../types';

export async function loadDemoShipments(): Promise<ShipmentInput[]> {
  const response = await fetch('/demo_shipments.csv');
  if (!response.ok) {
    throw new Error('Unable to load demo shipments CSV');
  }
  const csv = await response.text();
  return parseShipmentsCsv(csv);
}

export function parseShipmentsCsv(csv: string): ShipmentInput[] {
  const lines = csv.trim().split(/\r?\n/);
  const headers = splitCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = splitCsvLine(line);
    const row = Object.fromEntries(headers.map((header, index) => [header, values[index] || '']));
    return {
      shipment_id: row.shipment_id,
      supplier: row.supplier,
      origin: row.origin,
      destination: row.destination,
      route_nodes: row.route_nodes ? row.route_nodes.split('|').filter(Boolean) : [],
      imo_number: row.imo_number || null,
      mmsi: row.mmsi || null,
      vessel_name: row.vessel_name || null,
      vessel_latitude: toNumberOrNull(row.vessel_latitude),
      vessel_longitude: toNumberOrNull(row.vessel_longitude),
      vessel_status: row.vessel_status || null,
      vessel_speed_knots: toNumberOrNull(row.vessel_speed_knots),
      vessel_course_degrees: toNumberOrNull(row.vessel_course_degrees),
      vessel_progress_percent: toNumberOrNull(row.vessel_progress_percent),
      flight_callsign: row.flight_callsign || null,
      flight_icao24: row.flight_icao24 || null,
      flight_altitude_m: toNumberOrNull(row.flight_altitude_m),
      transport_mode: row.transport_mode || 'sea',
      material: row.material,
      quantity: toNumber(row.quantity),
      lead_time_days: toNumber(row.lead_time_days),
      inventory_days_cover: toNumber(row.inventory_days_cover),
      supplier_delay_count: toNumber(row.supplier_delay_count),
      priority: row.priority || 'normal',
      declared_value_usd: toNumber(row.declared_value_usd),
      departure_date: row.departure_date || null,
      eta_date: row.eta_date || null,
    };
  });
}

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      values.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  values.push(current);
  return values.map((value) => value.trim());
}

function toNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toNumberOrNull(value: string): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
