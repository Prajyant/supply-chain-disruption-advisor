/**
 * VesselWatchlist — Sidebar list of all tracked vessels with status indicators.
 *
 * Features:
 * - Status indicators: 🟢 active, 🟡 stale, 🔴 silent/danger
 * - Search and filter by status/region/linked-supplier
 * - Click to select vessel and show route on map
 */

import { useState, useMemo } from 'react';
import { Ship, Search, Filter, Eye, EyeOff } from 'lucide-react';
import { useVesselStore } from '../store/vesselStore';
import type { VesselStatus } from '../types/vessel';

const STATUS_ICONS: Record<string, string> = {
  active: '🟢',
  stale: '🟡',
  silent: '🔴',
  danger: '🔴',
  unknown: '⚪',
};

const STATUS_LABELS: Record<string, string> = {
  active: 'Active',
  stale: 'Stale',
  silent: 'AIS Silent',
  danger: 'Danger Zone',
  unknown: 'Unknown',
};

interface VesselWatchlistProps {
  onVesselSelect?: (imo: string) => void;
}

export function VesselWatchlist({ onVesselSelect }: VesselWatchlistProps) {
  const { vessels, selectedVessel, selectVessel, visibleRoutes, toggleRouteVisibility } = useVesselStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const filteredVessels = useMemo(() => {
    let result = vessels;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (v) =>
          v.name?.toLowerCase().includes(q) ||
          v.imo_number.includes(q) ||
          v.linked_supplier?.toLowerCase().includes(q)
      );
    }

    if (statusFilter !== 'all') {
      result = result.filter((v) => v.status === statusFilter);
    }

    return result;
  }, [vessels, searchQuery, statusFilter]);

  const handleSelect = (vessel: VesselStatus) => {
    selectVessel(vessel.imo_number);
    onVesselSelect?.(vessel.imo_number);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 border-r border-gray-700">
      {/* Header */}
      <div className="p-3 border-b border-gray-700">
        <div className="flex items-center gap-2 mb-2">
          <Ship className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-semibold text-white">Vessel Watchlist</h3>
          <span className="ml-auto text-xs text-gray-400">{vessels.length}</span>
        </div>

        {/* Search */}
        <div className="relative mb-2">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-500" />
          <input
            type="text"
            placeholder="Search vessels..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-7 pr-2 py-1 text-xs bg-gray-800 border border-gray-600 rounded text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Status filter */}
        <div className="flex gap-1 flex-wrap">
          {['all', 'active', 'stale', 'silent', 'danger'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-2 py-0.5 text-xs rounded ${
                statusFilter === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {status === 'all' ? 'All' : STATUS_ICONS[status]}
            </button>
          ))}
        </div>
      </div>

      {/* Vessel list */}
      <div className="flex-1 overflow-y-auto">
        {filteredVessels.map((vessel) => (
          <div
            key={vessel.imo_number}
            onClick={() => handleSelect(vessel)}
            className={`px-3 py-2 border-b border-gray-800 cursor-pointer hover:bg-gray-800 transition-colors ${
              selectedVessel === vessel.imo_number ? 'bg-gray-800 border-l-2 border-l-blue-500' : ''
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="text-sm">{STATUS_ICONS[vessel.status] || '⚪'}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-white truncate">
                  {vessel.name || `IMO ${vessel.imo_number}`}
                </p>
                <p className="text-xs text-gray-500">
                  {vessel.speed?.toFixed(1)} kts • {vessel.destination || 'No dest'}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  toggleRouteVisibility(vessel.imo_number);
                }}
                className="p-1 rounded hover:bg-gray-700"
                title={visibleRoutes.has(vessel.imo_number) ? 'Hide route' : 'Show route'}
              >
                {visibleRoutes.has(vessel.imo_number) ? (
                  <Eye className="w-3 h-3 text-blue-400" />
                ) : (
                  <EyeOff className="w-3 h-3 text-gray-500" />
                )}
              </button>
            </div>
            {vessel.linked_supplier && (
              <p className="text-xs text-gray-600 mt-0.5 pl-6">
                ↳ {vessel.linked_supplier}
              </p>
            )}
            {vessel.in_danger_zone && (
              <p className="text-xs text-red-400 mt-0.5 pl-6">
                ⚠ {vessel.in_danger_zone}
              </p>
            )}
          </div>
        ))}

        {filteredVessels.length === 0 && (
          <div className="p-4 text-center text-xs text-gray-500">
            {vessels.length === 0 ? 'No vessels in watchlist' : 'No vessels match filter'}
          </div>
        )}
      </div>
    </div>
  );
}
