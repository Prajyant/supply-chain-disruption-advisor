import { useQuery } from '@tanstack/react-query';
import { shipmentApi } from '../services/api';
import { ShipmentSummary, ShipmentStatus } from '../types';
import { Truck, Package, Clock, MapPin, AlertTriangle } from 'lucide-react';

const statusConfig: Record<ShipmentStatus, { label: string; color: string; bg: string; dot: string }> = {
  in_transit: { label: 'In Transit', color: 'text-blue-400', bg: 'bg-blue-500/10', dot: 'bg-blue-400' },
  delivered: { label: 'Delivered', color: 'text-emerald-400', bg: 'bg-emerald-500/10', dot: 'bg-emerald-400' },
  rerouted: { label: 'Rerouted', color: 'text-amber-400', bg: 'bg-amber-500/10', dot: 'bg-amber-400' },
  cancelled: { label: 'Cancelled', color: 'text-red-400', bg: 'bg-red-500/10', dot: 'bg-red-400' },
  delayed: { label: 'Delayed', color: 'text-orange-400', bg: 'bg-orange-500/10', dot: 'bg-orange-400' },
};

export function ShipmentTracker() {
  const { data: shipments, isLoading } = useQuery<ShipmentSummary[]>({
    queryKey: ['shipments'],
    queryFn: () => shipmentApi.getShipments().then((r) => r.data),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Truck className="w-5 h-5 text-indigo-400" /> Shipment Tracker
        </h3>
        <div className="space-y-3 animate-pulse">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 bg-slate-800 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const items = shipments || [];
  const activeCount = items.filter((s) => s.status === 'in_transit').length;
  const alertCount = items.filter((s) =>
    ['delayed', 'rerouted', 'cancelled'].includes(s.status)
  ).length;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Truck className="w-5 h-5 text-indigo-400" /> Shipment Tracker
        </h3>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-blue-400">{activeCount} active</span>
          {alertCount > 0 && (
            <span className="flex items-center gap-1 text-orange-400">
              <AlertTriangle className="w-3 h-3" /> {alertCount} alerts
            </span>
          )}
        </div>
      </div>

      {items.length > 0 ? (
        <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
          {items.map((s) => {
            const cfg = statusConfig[s.status as ShipmentStatus] || statusConfig.in_transit;
            return (
              <div
                key={s.shipment_id}
                className="shipment-card group"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${cfg.dot} ${
                      s.status === 'in_transit' ? 'animate-pulse' : ''
                    }`} />
                    <span className="text-sm font-medium text-white">{s.material || 'Shipment'}</span>
                  </div>
                  <span className={`status-badge ${cfg.color} ${cfg.bg}`}>{cfg.label}</span>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-400">
                  <div className="flex items-center gap-1">
                    <Package className="w-3 h-3 shrink-0" />
                    <span className="truncate">{s.supplier}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3 shrink-0" />
                    <span>{s.eta_days > 0 ? `${s.eta_days}d ETA` : 'Delivered'}</span>
                  </div>
                  {s.origin && (
                    <div className="flex items-center gap-1 col-span-2">
                      <MapPin className="w-3 h-3 shrink-0" />
                      <span className="truncate">{s.origin}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-8">
          <Truck className="w-10 h-10 text-slate-700 mx-auto mb-2" />
          <p className="text-sm text-slate-500">No shipments tracked yet.</p>
          <p className="text-xs text-slate-600 mt-1">Ingest data to start tracking.</p>
        </div>
      )}
    </div>
  );
}
