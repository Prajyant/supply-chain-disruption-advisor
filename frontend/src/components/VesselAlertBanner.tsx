/**
 * VesselAlertBanner — Alert banner for vessel anomalies.
 *
 * Shows recent vessel alerts (AIS silence, danger zone entry, speed anomaly)
 * with severity-based styling and dismiss functionality.
 */

import { AlertTriangle, Radio, Gauge, MapPin, X } from 'lucide-react';
import { useVesselStore } from '../store/vesselStore';
import type { VesselAnomaly } from '../types/vessel';

const ANOMALY_ICONS: Record<string, typeof AlertTriangle> = {
  ais_silence: Radio,
  speed_anomaly: Gauge,
  danger_zone_entry: MapPin,
};

const SEVERITY_STYLES: Record<string, string> = {
  high: 'bg-red-900/50 border-red-700 text-red-200',
  medium: 'bg-yellow-900/50 border-yellow-700 text-yellow-200',
  low: 'bg-blue-900/50 border-blue-700 text-blue-200',
  critical: 'bg-red-900/80 border-red-500 text-red-100',
};

export function VesselAlertBanner() {
  const { anomalies, clearAnomalies } = useVesselStore();

  if (anomalies.length === 0) return null;

  // Show only the 3 most recent
  const recentAnomalies = anomalies.slice(0, 3);

  return (
    <div className="space-y-1 mb-3">
      <div className="flex items-center justify-between px-2">
        <span className="text-xs text-gray-400 font-medium">
          Vessel Alerts ({anomalies.length})
        </span>
        <button
          onClick={clearAnomalies}
          className="text-xs text-gray-500 hover:text-white"
        >
          Clear all
        </button>
      </div>

      {recentAnomalies.map((anomaly, idx) => (
        <AlertItem key={`${anomaly.imo_number}-${anomaly.type}-${idx}`} anomaly={anomaly} />
      ))}
    </div>
  );
}

function AlertItem({ anomaly }: { anomaly: VesselAnomaly }) {
  const Icon = ANOMALY_ICONS[anomaly.type] || AlertTriangle;
  const style = SEVERITY_STYLES[anomaly.severity] || SEVERITY_STYLES.medium;

  return (
    <div className={`flex items-start gap-2 px-3 py-2 rounded border ${style}`}>
      <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate">{anomaly.message}</p>
        <p className="text-xs opacity-70 truncate">{anomaly.details}</p>
      </div>
      <span className="text-[10px] opacity-60 whitespace-nowrap">
        {new Date(anomaly.timestamp).toLocaleTimeString()}
      </span>
    </div>
  );
}
