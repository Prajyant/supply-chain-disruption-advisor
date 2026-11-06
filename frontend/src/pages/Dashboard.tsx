import { useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { shipmentApi } from '../services/api';
import { loadDemoShipments } from '../services/shipmentData';
import { trackVessel } from '../services/vesselApi';
import {
  AlertTriangle, Activity, RefreshCw, Ship, Radio,
  Upload, ChevronRight, TrendingUp, Package, Loader2, Plus, X,
} from 'lucide-react';
import { useViewMode } from '../context/ViewModeContext';
import { CFODashboard } from './CFODashboard';
import { OperationsDashboard } from './OperationsDashboard';
import { useShipmentStore } from '../store/shipmentStore';

export function Dashboard() {
  const { viewMode } = useViewMode();
  const [selectedShipmentId, setSelectedShipmentId] = useState('');
  const { uploadedShipments, setUploadedShipments } = useShipmentStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Quick track ship modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newIdentifier, setNewIdentifier] = useState('');
  const [newName, setNewName] = useState('');
  const [newSupplier, setNewSupplier] = useState('');
  const [newOrigin, setNewOrigin] = useState('');
  const [newDestination, setNewDestination] = useState('');
  const [newMaterial, setNewMaterial] = useState('');
  const [isSubmittingShip, setIsSubmittingShip] = useState(false);

  const { data: risks, isLoading, error, refetch } = useQuery({
    queryKey: ['risk-summary'],
    queryFn: () => shipmentApi.getRiskSummary().then((res) => res.data),
    refetchInterval: 15_000,
  });

  const { data: demoShipments = [], isLoading: shipmentsLoading, refetch: refetchShipments } = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
    refetchInterval: 15_000,
  });

  const handleAddShip = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newIdentifier.trim()) return;
    setIsSubmittingShip(true);
    try {
      await trackVessel({
        identifier: newIdentifier.trim(),
        vessel_name: newName.trim(),
        linked_supplier: newSupplier.trim(),
        origin: newOrigin.trim() || 'Shanghai',
        destination: newDestination.trim() || 'Rotterdam',
        material: newMaterial.trim() || 'Containerized Electronics & Cargo',
      });
      setNewIdentifier('');
      setNewName('');
      setNewSupplier('');
      setNewOrigin('');
      setNewDestination('');
      setNewMaterial('');
      setShowAddModal(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['demo-shipments'] }),
        queryClient.invalidateQueries({ queryKey: ['risk-summary'] }),
      ]);
    } catch (err: any) {
      alert(`Failed to track vessel: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsSubmittingShip(false);
    }
  };

  const shipments = uploadedShipments
    ? [...demoShipments, ...uploadedShipments.filter(u => !demoShipments.some(d => d.shipment_id === u.shipment_id))]
    : demoShipments;

  const uploadCsv = useMutation({
    mutationFn: (file: File) => shipmentApi.uploadCsv(file).then((res) => res.data),
    onSuccess: (data) => {
      setUploadedShipments(data.shipments);
      setSelectedShipmentId('');
      shipmentApi.preloadAnalyses(data.shipments).then(() => refetch());
    },
  });

  const selectedShipment = useMemo(
    () => shipments.find((s) => s.shipment_id === selectedShipmentId) || shipments[0],
    [shipments, selectedShipmentId],
  );

  if (viewMode === 'cfo')        return <CFODashboard />;
  if (viewMode === 'operations') return <OperationsDashboard />;

  const metrics = [
    {
      label: 'Shipments Analyzed',
      value: risks?.total_analyzed ?? 0,
      icon: Ship,
      accent: 'text-primary-400',
      bg: 'bg-primary-500/10',
      border: 'border-primary-500/20',
    },
    {
      label: 'Critical Risk',
      value: risks?.critical ?? 0,
      icon: AlertTriangle,
      accent: 'text-red-400',
      bg: 'bg-red-500/10',
      border: 'border-red-500/20',
    },
    {
      label: 'High Risk',
      value: risks?.high ?? 0,
      icon: TrendingUp,
      accent: 'text-orange-400',
      bg: 'bg-orange-500/10',
      border: 'border-orange-500/20',
    },
    {
      label: 'Avg Risk Score',
      value: risks?.avg_risk_score?.toFixed(2) ?? '0.00',
      icon: Radio,
      accent: 'text-amber-400',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/20',
    },
  ];

  if (isLoading) {
    return (
      <div className="p-8 space-y-6">
        <div className="skeleton h-8 w-48 rounded-lg" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-24 rounded-xl" />)}
        </div>
        <div className="skeleton h-72 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="alert-critical rounded-xl">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-white">Failed to load risk data</p>
            <p className="text-sm mt-0.5 opacity-80">Check the backend is running, then refresh.</p>
          </div>
          <button onClick={() => refetch()} className="ml-auto btn-secondary text-xs py-1.5 px-3">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-7">

      {/* ── Page header ── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="page-title">Risk Dashboard</h1>
          <p className="page-subtitle">
            Shipment risk scoring via Strands, XGBoost, Bedrock, vessel, weather and trade signals
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => { refetch(); refetchShipments(); }} className="btn-secondary flex items-center gap-2 text-sm">
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* ── Metric tiles ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className={`card border ${m.border} flex items-center justify-between gap-4`}>
              <div>
                <p className="stat-label">{m.label}</p>
                <p className="stat-value mt-1">{m.value}</p>
              </div>
              <div className={`w-11 h-11 rounded-xl ${m.bg} flex items-center justify-center shrink-0`}>
                <Icon className={`w-5 h-5 ${m.accent}`} />
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Shipment feed ── */}
      <div className="card !p-0 overflow-hidden">
        {/* Table header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div>
            <h2 className="section-title flex items-center gap-2">
              <Package className="w-4 h-4 text-slate-400" />
              Live Fleet & Shipment Feed
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {uploadedShipments
                ? `Live fleet tracking + ${uploadedShipments.length} custom uploaded`
                : 'Live fleet tracking'}
              {' '}· {shipments.length} active shipments
            </p>
          </div>
          <div className="flex items-center gap-3">
            {uploadCsv.isPending && (
              <span className="flex items-center gap-1.5 text-xs text-slate-400">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Uploading…
              </span>
            )}
            <button
              className="bg-blue-600 hover:bg-blue-500 text-white font-medium px-3 py-1.5 rounded-lg flex items-center gap-1.5 text-sm transition-colors"
              onClick={() => setShowAddModal(true)}
            >
              <Plus className="w-3.5 h-3.5" />
              Track Vessel
            </button>
            <button
              className="btn-secondary flex items-center gap-2 text-sm"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="w-3.5 h-3.5" />
              Upload CSV
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadCsv.mutate(file);
                e.target.value = '';
              }}
            />
          </div>
        </div>

        {/* Modal: Track Vessel */}
        {showAddModal && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 w-full max-w-md shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Ship className="w-5 h-5 text-blue-400" />
                  <h3 className="font-semibold text-white text-base">Add Vessel to Real-Time Tracking</h3>
                </div>
                <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleAddShip} className="space-y-3 text-sm">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    IMO or MMSI Number <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 9811000 or 353136000"
                    value={newIdentifier}
                    onChange={(e) => setNewIdentifier(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:border-blue-500 focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">Vessel Name</label>
                    <input
                      type="text"
                      placeholder="e.g. EVER GIVEN"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">Carrier / Supplier</label>
                    <input
                      type="text"
                      placeholder="e.g. Evergreen Marine"
                      value={newSupplier}
                      onChange={(e) => setNewSupplier(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">Origin Port</label>
                    <input
                      type="text"
                      placeholder="Shanghai"
                      value={newOrigin}
                      onChange={(e) => setNewOrigin(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">Destination Port</label>
                    <input
                      type="text"
                      placeholder="Rotterdam"
                      value={newDestination}
                      onChange={(e) => setNewDestination(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Cargo / Material</label>
                  <input
                    type="text"
                    placeholder="e.g. Semiconductors & Components"
                    value={newMaterial}
                    onChange={(e) => setNewMaterial(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="px-3 py-1.5 text-slate-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingShip}
                    className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-4 py-1.5 rounded-lg flex items-center gap-1.5"
                  >
                    {isSubmittingShip && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Start Tracking
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {shipmentsLoading ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, i) => <div key={i} className="skeleton h-10 rounded-lg" />)}
          </div>
        ) : shipments.length === 0 ? (
          <div className="empty-state">
            <Ship className="empty-state-icon" />
            <p className="empty-state-title">No shipments loaded</p>
            <p className="empty-state-body">Upload a CSV or wait for data ingestion to complete.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-900/60">
                  <th className="table-header">Shipment</th>
                  <th className="table-header">Supplier</th>
                  <th className="table-header">Route</th>
                  <th className="table-header">Mode</th>
                  <th className="table-header">Priority</th>
                  <th className="table-header text-right">Inventory</th>
                  <th className="table-header" />
                </tr>
              </thead>
              <tbody>
                {shipments.map((shipment) => {
                  const isSelected = selectedShipment?.shipment_id === shipment.shipment_id;
                  return (
                    <tr
                      key={shipment.shipment_id}
                      onClick={() => {
                        setSelectedShipmentId(shipment.shipment_id);
                        navigate(`/shipments/${shipment.shipment_id}`);
                      }}
                      className={`table-row border-b border-slate-800/60 ${isSelected ? 'bg-primary-600/8 border-l-2 border-l-primary-500' : ''}`}
                    >
                      <td className="table-cell">
                        <div className="flex items-center gap-2">
                          <span className="mono font-semibold text-sky-400">{shipment.shipment_id}</span>
                          {shipment.vessel_status && (
                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${
                              shipment.vessel_status.includes('DANGER') ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                              shipment.vessel_status.includes('SILENT') ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                              'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            }`}>
                              <span className="w-1.5 h-1.5 rounded-full mr-1 bg-current animate-pulse" />
                              {shipment.vessel_status}
                            </span>
                          )}
                        </div>
                        {shipment.vessel_name && (
                          <div className="text-[11px] text-slate-400 flex items-center gap-1.5 mt-0.5">
                            <Ship className="w-3 h-3 text-slate-500" />
                            <span className="font-medium text-slate-300">{shipment.vessel_name}</span>
                            {shipment.vessel_speed_knots !== undefined && shipment.vessel_speed_knots !== null && (
                              <span className="text-slate-500 font-mono">· {shipment.vessel_speed_knots.toFixed(1)} kts</span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="table-cell font-medium text-white">{shipment.supplier}</td>
                      <td className="table-cell text-slate-400">
                        {shipment.origin}
                        <span className="mx-1.5 text-slate-700">→</span>
                        {shipment.destination}
                      </td>
                      <td className="table-cell">
                        <span className="badge-neutral">{shipment.transport_mode || '—'}</span>
                      </td>
                      <td className="table-cell">
                        <span className={`badge ${
                          shipment.priority === 'critical' ? 'badge-critical' :
                          shipment.priority === 'high'     ? 'badge-high' :
                          shipment.priority === 'medium'   ? 'badge-medium' : 'badge-low'
                        }`}>{shipment.priority || '—'}</span>
                      </td>
                      <td className="table-cell text-right tabular-nums">
                        <span className={
                          (shipment.inventory_days_cover ?? 99) <= 7  ? 'text-red-400 font-semibold' :
                          (shipment.inventory_days_cover ?? 99) <= 14 ? 'text-amber-400 font-semibold' :
                          'text-slate-300'
                        }>
                          {shipment.inventory_days_cover ?? '—'}d
                        </span>
                      </td>
                      <td className="table-cell">
                        <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Table footer */}
        {shipments.length > 0 && (
          <div className="px-6 py-3 border-t border-slate-800 flex items-center justify-between">
            <p className="text-xs text-slate-600">Click any row to open the full shipment analysis</p>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Activity className="w-3.5 h-3.5" />
              Auto-refreshes every 30s
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
