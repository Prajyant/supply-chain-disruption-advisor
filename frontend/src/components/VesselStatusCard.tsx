/**
 * VesselStatusCard — Detail card showing full vessel information.
 *
 * Displays: IMO, MMSI, speed, course, destination, ETA, linked supplier, risk level.
 */

import { Ship, Navigation, Anchor, AlertTriangle, ExternalLink } from 'lucide-react';
import type { VesselStatus } from '../types/vessel';

interface VesselStatusCardProps {
  vessel: VesselStatus;
  onClose?: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-500',
  stale: 'bg-yellow-500',
  silent: 'bg-red-500',
  danger: 'bg-red-600',
  unknown: 'bg-gray-500',
};

export function VesselStatusCard({ vessel, onClose }: VesselStatusCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 shadow-xl max-w-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Ship className="w-5 h-5 text-blue-400" />
          <h3 className="text-sm font-bold text-white">{vessel.name || 'Unknown Vessel'}</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[vessel.status]}`} />
          <span className="text-xs text-gray-400 capitalize">{vessel.status}</span>
          {onClose && (
            <button onClick={onClose} className="text-gray-500 hover:text-white text-xs ml-2">✕</button>
          )}
        </div>
      </div>

      {/* Identity */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mb-3">
        <div className="text-gray-500">IMO</div>
        <div className="text-white font-mono">{vessel.imo_number}</div>
        <div className="text-gray-500">MMSI</div>
        <div className="text-white font-mono">{vessel.mmsi || 'N/A'}</div>
        <div className="text-gray-500">Type</div>
        <div className="text-white">{vessel.vessel_type || 'Unknown'}</div>
        <div className="text-gray-500">Flag</div>
        <div className="text-white">{vessel.flag || 'N/A'}</div>
      </div>

      {/* Navigation */}
      <div className="border-t border-gray-700 pt-2 mb-3">
        <div className="flex items-center gap-1 mb-1">
          <Navigation className="w-3 h-3 text-blue-400" />
          <span className="text-xs text-gray-400">Navigation</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div className="text-gray-500">Speed</div>
          <div className="text-white">{vessel.speed?.toFixed(1) || '0'} kts</div>
          <div className="text-gray-500">Course</div>
          <div className="text-white">{vessel.course?.toFixed(1) || '0'}°</div>
          <div className="text-gray-500">Heading</div>
          <div className="text-white">{vessel.heading?.toFixed(1) || '0'}°</div>
          <div className="text-gray-500">Position</div>
          <div className="text-white font-mono text-[10px]">
            {vessel.latitude?.toFixed(4)}N, {vessel.longitude?.toFixed(4)}E
          </div>
        </div>
      </div>

      {/* Destination */}
      <div className="border-t border-gray-700 pt-2 mb-3">
        <div className="flex items-center gap-1 mb-1">
          <Anchor className="w-3 h-3 text-blue-400" />
          <span className="text-xs text-gray-400">Voyage</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div className="text-gray-500">Destination</div>
          <div className="text-white">{vessel.destination || 'Not declared'}</div>
          <div className="text-gray-500">ETA</div>
          <div className="text-white">{vessel.eta || 'Unknown'}</div>
        </div>
      </div>

      {/* Alerts */}
      {vessel.in_danger_zone && (
        <div className="border-t border-gray-700 pt-2 mb-3">
          <div className="flex items-center gap-1 text-red-400">
            <AlertTriangle className="w-3 h-3" />
            <span className="text-xs font-medium">In danger zone: {vessel.in_danger_zone}</span>
          </div>
        </div>
      )}

      {/* Links */}
      {(vessel.linked_supplier || vessel.linked_shipment_id) && (
        <div className="border-t border-gray-700 pt-2">
          <div className="flex items-center gap-1 mb-1">
            <ExternalLink className="w-3 h-3 text-blue-400" />
            <span className="text-xs text-gray-400">Links</span>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {vessel.linked_supplier && (
              <>
                <div className="text-gray-500">Supplier</div>
                <div className="text-blue-400">{vessel.linked_supplier}</div>
              </>
            )}
            {vessel.linked_shipment_id && (
              <>
                <div className="text-gray-500">Shipment</div>
                <div className="text-blue-400">{vessel.linked_shipment_id}</div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
