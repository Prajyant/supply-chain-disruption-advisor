import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { shipmentApi } from '../services/api';
import { loadDemoShipments } from '../services/shipmentData';
import {
  AlertTriangle,
  Activity,
  RefreshCw,
  Ship,
  Radio,
  Upload,
} from 'lucide-react';
import { useViewMode } from '../context/ViewModeContext';
import { CFODashboard } from './CFODashboard';
import { OperationsDashboard } from './OperationsDashboard';
import { useShipmentStore } from '../store/shipmentStore';

export function Dashboard() {
  const { viewMode } = useViewMode();

  // All hooks must be called before conditional returns (React rules of hooks)
  const [selectedShipmentId, setSelectedShipmentId] = useState('');
  const { uploadedShipments, setUploadedShipments } = useShipmentStore();
  const navigate = useNavigate();

  const { data: risks, isLoading, error, refetch } = useQuery({
    queryKey: ['risk-summary'],
    queryFn: () => shipmentApi.getRiskSummary().then((res) => res.data),
    refetchInterval: 30_000,
  });

  const { data: demoShipments = [], isLoading: shipmentsLoading } = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
  });

  const shipments = uploadedShipments
    ? [...demoShipments, ...uploadedShipments.filter(u => !demoShipments.some(d => d.shipment_id === u.shipment_id))]
    : demoShipments;

  const uploadCsv = useMutation({
    mutationFn: (file: File) => shipmentApi.uploadCsv(file).then((res) => res.data),
    onSuccess: (data) => {
      setUploadedShipments(data.shipments);
      setSelectedShipmentId('');
      // Trigger background analysis for uploaded shipments so metrics update
      shipmentApi.preloadAnalyses(data.shipments).then(() => refetch());
    },
  });

  const selectedShipment = useMemo(
    () => shipments.find((shipment) => shipment.shipment_id === selectedShipmentId) || shipments[0],
    [shipments, selectedShipmentId]
  );

  // Delegate to role-specific views (after all hooks)
  if (viewMode === 'cfo')        return <CFODashboard />;
  if (viewMode === 'operations') return <OperationsDashboard />;

  const metrics = [
    {
      label: 'Shipments Analyzed',
      value: risks?.total_analyzed ?? 0,
      icon: Ship,
      color: 'text-primary-400',
      bgColor: 'bg-primary-500/10',
    },
    {
      label: 'Critical Risk',
      value: risks?.critical ?? 0,
      icon: AlertTriangle,
      color: 'text-danger-400',
      bgColor: 'bg-danger-500/10',
    },
    {
      label: 'High Risk',
      value: risks?.high ?? 0,
      icon: Activity,
      color: 'text-orange-400',
      bgColor: 'bg-orange-500/10',
    },
    {
      label: 'Avg Risk Score',
      value: risks?.avg_risk_score?.toFixed(2) ?? '0.00',
      icon: Radio,
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-500/10',
    },
  ];

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-800 rounded w-1/4" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-slate-800 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="card border-danger-500">
          <p className="text-danger-400">Failed to load risks. Please try again.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400">Shipment risk testing with Strands, XGBoost, Bedrock, vessel, weather, and trade signals</p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div key={metric.label} className="card min-h-[6rem]">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400 mb-1">{metric.label}</p>
                  <p className="text-3xl font-bold text-white">{metric.value}</p>
                </div>
                <div className={`p-3 rounded-lg ${metric.bgColor}`}>
                  <Icon className={`w-6 h-6 ${metric.color}`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <section className="grid grid-cols-1 gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-semibold text-white">Supplier Shipment Test Feed</h2>
              <p className="text-sm text-slate-400">
                {uploadedShipments ? `Demo + ${uploadedShipments.length} uploaded` : 'Loaded from demo_shipments.csv'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <Ship className="w-4 h-4 text-primary-400" />
                {shipments.length} shipments
              </div>
              <label className="btn-secondary flex items-center gap-2 cursor-pointer">
                <Upload className="w-4 h-4" />
                Upload CSV
                <input
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) uploadCsv.mutate(file);
                  }}
                />
              </label>
            </div>
          </div>

          {shipmentsLoading ? (
            <div className="h-40 rounded-lg bg-slate-800 animate-pulse" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-left text-slate-400">
                    <th className="pb-3 font-medium">Shipment</th>
                    <th className="pb-3 font-medium">Supplier</th>
                    <th className="pb-3 font-medium">Route</th>
                    <th className="pb-3 font-medium">Vessel</th>
                    <th className="pb-3 font-medium">Priority</th>
                    <th className="pb-3 font-medium">Inventory</th>
                  </tr>
                </thead>
                <tbody>
                  {shipments.map((shipment) => {
                    const selected = selectedShipment?.shipment_id === shipment.shipment_id;
                    return (
                      <tr
                        key={shipment.shipment_id}
                        onClick={() => {
                          setSelectedShipmentId(shipment.shipment_id);
                          navigate(`/shipments/${shipment.shipment_id}`);
                        }}
                        className={`cursor-pointer border-b border-slate-800/60 transition-colors ${
                          selected ? 'bg-primary-500/10 text-white' : 'text-slate-300 hover:bg-slate-800/60'
                        }`}
                      >
                        <td className="py-3 font-mono text-xs">{shipment.shipment_id}</td>
                        <td className="py-3">{shipment.supplier}</td>
                        <td className="py-3">{shipment.origin} to {shipment.destination}</td>
                        <td className="py-3">{shipment.vessel_name || shipment.imo_number || 'Live tracker'}</td>
                        <td className="py-3">{shipment.priority}</td>
                        <td className="py-3">{shipment.inventory_days_cover} days</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

    </div>
  );
}
