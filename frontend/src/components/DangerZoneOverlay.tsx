/**
 * DangerZoneOverlay — Semi-transparent polygon overlays on map for danger zones.
 *
 * Renders danger zones from the backend as Leaflet rectangles with
 * tooltips showing zone name and vessel count.
 */

import { Rectangle, Tooltip } from 'react-leaflet';
import { useVesselStore } from '../store/vesselStore';
import type { DangerZone } from '../types/vessel';

const ZONE_COLORS: Record<string, string> = {
  'Red Sea / Bab-el-Mandeb': '#ff3355',
  'Gulf of Aden': '#ff3355',
  'Strait of Hormuz': '#ff8800',
  'Gulf of Guinea': '#ff3355',
  'South China Sea': '#ff8800',
  'Malacca Strait': '#ff8800',
  'Somali Basin': '#ff3355',
};

export function DangerZoneOverlay() {
  const { dangerZones } = useVesselStore();

  if (!dangerZones || dangerZones.length === 0) return null;

  return (
    <>
      {dangerZones.map((zone: DangerZone) => {
        const color = ZONE_COLORS[zone.name] || '#ff8800';
        const bounds: [[number, number], [number, number]] = [
          [zone.lat_min, zone.lon_min],
          [zone.lat_max, zone.lon_max],
        ];

        return (
          <Rectangle
            key={zone.name}
            bounds={bounds}
            pathOptions={{
              color,
              weight: 1,
              fillOpacity: 0.06,
              opacity: 0.3,
            }}
          >
            <Tooltip sticky>
              <div className="text-xs">
                <strong>{zone.name}</strong>
                <br />
                Risk weight: {zone.risk_weight}
                {zone.vessel_count > 0 && (
                  <>
                    <br />
                    ⚠ {zone.vessel_count} vessel{zone.vessel_count > 1 ? 's' : ''} inside
                  </>
                )}
              </div>
            </Tooltip>
          </Rectangle>
        );
      })}
    </>
  );
}
