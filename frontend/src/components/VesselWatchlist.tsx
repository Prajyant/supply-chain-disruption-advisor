/**
 * VesselWatchlist — Real-time sidebar list of all tracked vessels.
 *
 * Features:
 * - Real-time status indicators: 🟢 active, 🟡 stale, 🔴 silent/danger
 * - Dynamic vessel tracking (add any vessel by IMO/MMSI without CSV)
 * - Quick untrack/delete
 * - Search and filter by status/name/IMO/supplier
 * - Click to select vessel and fly to position on map
 */

import { useState, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Ship, Search, Eye, EyeOff, Plus, Trash2, X, Navigation } from 'lucide-react';
import { useVesselStore } from '../store/vesselStore';
import { trackVessel, untrackVessel } from '../services/vesselApi';
import type { VesselStatus } from '../types/vessel';

const STATUS_ICONS: Record<string, string> = {
  active: '🟢',
  stale: '🟡',
  silent: '🔴',
  danger: '🔴',
  unknown: '⚪',
};

interface VesselWatchlistProps {
  onVesselSelect?: (imo: string) => void;
  onRefreshNeeded?: () => void;
}

export function VesselWatchlist({ onVesselSelect, onRefreshNeeded }: VesselWatchlistProps) {
  const queryClient = useQueryClient();
  const { vessels, setVessels, selectedVessel, selectVessel, visibleRoutes, toggleRouteVisibility } = useVesselStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newIdentifier, setNewIdentifier] = useState('');
  const [newName, setNewName] = useState('');
  const [newSupplier, setNewSupplier] = useState('');
  const [newShipmentId, setNewShipmentId] = useState('');
  const [newOrigin, setNewOrigin] = useState('');
  const [newDestination, setNewDestination] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const filteredVessels = useMemo(() => {
    let result = vessels;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (v) =>
          (v.name && v.name.toLowerCase().includes(q)) ||
          (v.imo_number && String(v.imo_number).toLowerCase().includes(q)) ||
          (v.mmsi && String(v.mmsi).toLowerCase().includes(q)) ||
          (v.linked_supplier && v.linked_supplier.toLowerCase().includes(q)) ||
          (v.destination && v.destination.toLowerCase().includes(q))
      );
    }

    if (statusFilter !== 'all') {
      result = result.filter((v) => v.status === statusFilter);
    }

    return result;
  }, [vessels, searchQuery, statusFilter]);

  const handleSelect = (vessel: VesselStatus) => {
    const id = vessel.imo_number || vessel.mmsi || '';
    selectVessel(id);
    onVesselSelect?.(id);
  };

  const handleAddVessel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newIdentifier.trim()) return;
    setIsSubmitting(true);
    try {
      const res = await trackVessel({
        identifier: newIdentifier.trim(),
        vessel_name: newName.trim(),
        linked_supplier: newSupplier.trim(),
        linked_shipment_id: newShipmentId.trim(),
        origin: newOrigin.trim() || undefined,
        destination: newDestination.trim() || undefined,
      });
      if (res.vessel) {
        setVessels([res.vessel, ...vessels.filter((v) => v.imo_number !== res.vessel.imo_number)]);
        selectVessel(res.vessel.imo_number);
        onVesselSelect?.(res.vessel.imo_number);
      }
      setNewIdentifier('');
      setNewName('');
      setNewSupplier('');
      setNewShipmentId('');
      setNewOrigin('');
      setNewDestination('');
      setShowAddModal(false);
      onRefreshNeeded?.();

      // Sync across entire app (Risk Dashboard, CFO, Operations, etc.)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['demo-shipments'] }),
        queryClient.invalidateQueries({ queryKey: ['shipments'] }),
        queryClient.invalidateQueries({ queryKey: ['risk-summary'] }),
        queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
      ]);
    } catch (err: any) {
      alert(`Failed to track vessel: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUntrack = async (e: React.MouseEvent, vessel: VesselStatus) => {
    e.stopPropagation();
    const id = vessel.imo_number || vessel.mmsi;
    if (!id) return;
    if (!confirm(`Untrack ${vessel.name || id}?`)) return;
    try {
      await untrackVessel(id);
      setVessels(vessels.filter((v) => v.imo_number !== id && v.mmsi !== id));
      if (selectedVessel === id) {
        selectVessel(null);
      }
      // Sync across entire app
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['demo-shipments'] }),
        queryClient.invalidateQueries({ queryKey: ['shipments'] }),
        queryClient.invalidateQueries({ queryKey: ['risk-summary'] }),
        queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
      ]);
    } catch (err: any) {
      alert(`Failed to untrack: ${err.message}`);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 border-r border-gray-700">
      {/* Header */}
      <div className="p-3 border-b border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Ship className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-semibold text-white">Live Fleet</h3>
            <span className="text-xs bg-slate-800 text-blue-300 font-mono px-1.5 py-0.5 rounded">
              {vessels.length}
            </span>
          </div>
          <button
            onClick={() => setShowAddModal(!showAddModal)}
            className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-500 text-white px-2 py-1 rounded font-medium transition"
            title="Track new vessel"
          >
            <Plus className="w-3 h-3" />
            Track
          </button>
        </div>

        {/* Add Vessel Form Dropdown */}
        {showAddModal && (
          <form onSubmit={handleAddVessel} className="mb-3 p-2.5 bg-slate-950 border border-slate-700 rounded-lg space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">Track Live Vessel</span>
              <button type="button" onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <input
              type="text"
              placeholder="IMO or MMSI number *"
              required
              value={newIdentifier}
              onChange={(e) => setNewIdentifier(e.target.value)}
              className="w-full px-2 py-1 text-xs bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <input
              type="text"
              placeholder="Vessel Name (optional)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full px-2 py-1 text-xs bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
            <div className="flex gap-1.5">
              <input
                type="text"
                placeholder="Linked Supplier"
                value={newSupplier}
                onChange={(e) => setNewSupplier(e.target.value)}
                className="w-1/2 px-2 py-1 text-xs bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <input
                type="text"
                placeholder="Shipment ID"
                value={newShipmentId}
                onChange={(e) => setNewShipmentId(e.target.value)}
                className="w-1/2 px-2 py-1 text-xs bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex gap-1.5">
              <input
                type="text"
                placeholder="Origin (e.g. Shanghai)"
                value={newOrigin}
                onChange={(e) => setNewOrigin(e.target.value)}
                className="w-1/2 px-2 py-1 text-xs bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <input
                type="text"
                placeholder="Destination (e.g. Rotterdam)"
                value={newDestination}
                onChange={(e) => setNewDestination(e.target.value)}
                className="w-1/2 px-2 py-1 text-xs bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-1 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded font-medium disabled:opacity-50"
            >
              {isSubmitting ? 'Tracking...' : 'Start Real-Time Tracking'}
            </button>
          </form>
        )}

        {/* Search */}
        <div className="relative mb-2">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-500" />
          <input
            type="text"
            placeholder="Search fleet (name, IMO, supplier)..."
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
              className={`px-2 py-0.5 text-xs rounded transition ${
                statusFilter === status
                  ? 'bg-blue-600 text-white font-medium'
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
        {filteredVessels.map((vessel, index) => {
          const vesselId = vessel.imo_number || vessel.mmsi || `vessel-${index}`;
          const isSelected = selectedVessel === vessel.imo_number || selectedVessel === vessel.mmsi;
          const hasPosition = Number.isFinite(vessel.latitude) && Number.isFinite(vessel.longitude) && (vessel.latitude !== 0 || vessel.longitude !== 0);

          return (
            <div
              key={vesselId}
              onClick={() => handleSelect(vessel)}
              className={`px-3 py-2 border-b border-gray-800/80 cursor-pointer hover:bg-gray-800/80 transition-colors ${
                isSelected ? 'bg-slate-800 border-l-2 border-l-blue-500' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm shrink-0">{STATUS_ICONS[vessel.status] || '⚪'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-1">
                    <p className="text-xs font-medium text-white truncate">
                      {vessel.name || `IMO ${vessel.imo_number}`}
                    </p>
                    <span className="text-[10px] font-mono text-slate-500 shrink-0">
                      {vessel.imo_number || vessel.mmsi}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-gray-400">
                    <span className="flex items-center gap-0.5 text-emerald-400">
                      <Navigation className="w-2.5 h-2.5" />
                      {vessel.speed !== undefined && vessel.speed !== null ? `${vessel.speed.toFixed(1)} kts` : '0 kts'}
                    </span>
                    <span>•</span>
                    <span className="truncate">
                      {vessel.destination || (hasPosition ? `${vessel.latitude.toFixed(2)}°, ${vessel.longitude.toFixed(2)}°` : 'Awaiting AIS')}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleRouteVisibility(vessel.imo_number || vessel.mmsi || '');
                    }}
                    className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
                    title={visibleRoutes.has(vessel.imo_number) ? 'Hide track' : 'Show track'}
                  >
                    {visibleRoutes.has(vessel.imo_number) ? (
                      <Eye className="w-3.5 h-3.5 text-blue-400" />
                    ) : (
                      <EyeOff className="w-3.5 h-3.5 text-gray-500" />
                    )}
                  </button>
                  <button
                    onClick={(e) => handleUntrack(e, vessel)}
                    className="p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400"
                    title="Untrack vessel"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
              {vessel.linked_supplier && (
                <p className="text-[11px] text-slate-400 mt-1 pl-6 truncate">
                  ↳ <span className="text-slate-300 font-medium">{vessel.linked_supplier}</span>
                  {vessel.linked_shipment_id && (
                    <span className="ml-1 text-sky-400 font-mono">({vessel.linked_shipment_id})</span>
                  )}
                </p>
              )}
              {vessel.in_danger_zone && (
                <p className="text-[11px] text-red-400 font-medium mt-0.5 pl-6 flex items-center gap-1">
                  <span>⚠</span> {vessel.in_danger_zone}
                </p>
              )}
            </div>
          );
        })}

        {filteredVessels.length === 0 && (
          <div className="p-6 text-center text-xs text-gray-500 space-y-2">
            <p>{vessels.length === 0 ? 'No tracked vessels yet.' : 'No vessels match current filter.'}</p>
            {vessels.length === 0 && (
              <button
                onClick={() => setShowAddModal(true)}
                className="text-blue-400 hover:text-blue-300 underline"
              >
                Track your first vessel
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
