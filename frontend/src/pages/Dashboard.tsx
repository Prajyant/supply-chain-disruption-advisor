import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { riskApi, shipmentApi } from '../services/api';
import { ShipmentTracker } from '../components/ShipmentTracker';
import { loadDemoShipments } from '../services/shipmentData';
import { useRiskStore } from '../store/riskStore';
import { RiskCard } from '../components/RiskCard';
import { ShipmentInput, StrandsShipmentRiskResponse } from '../types';
import {
  AlertTriangle,
  TrendingUp,
  Activity,
  Clock,
  RefreshCw,
  Ship,
  Radio,
  Route,
  Zap,
  CheckCircle2,
  Upload,
} from 'lucide-react';
import { useViewMode } from '../context/ViewModeContext';
import { CFODashboard } from './CFODashboard';
import { OperationsDashboard } from './OperationsDashboard';

export function Dashboard() {
  const { viewMode } = useViewMode();

  // Delegate to role-specific views
  if (viewMode === 'cfo')        return <CFODashboard />;
  if (viewMode === 'operations') return <OperationsDashboard />;

  // Analyst view (default) ↓
  const [selectedShipmentId, setSelectedShipmentId] = useState('');
  const [riskResult, setRiskResult] = useState<StrandsShipmentRiskResponse | null>(null);
  const [uploadedShipments, setUploadedShipments] = useState<ShipmentInput[] | null>(null);
  const navigate = useNavigate();

  const { data: risks, isLoading, error, refetch } = useQuery({
    queryKey: ['risks'],
    queryFn: () => riskApi.getRisks().then((res) => res.data),
  });

  const { data: demoShipments = [], isLoading: shipmentsLoading } = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
  });

  const shipments = uploadedShipments || demoShipments;

  const uploadCsv = useMutation({
    mutationFn: (file: File) => shipmentApi.uploadCsv(file).then((res) => res.data),
    onSuccess: (data) => {
      setUploadedShipments(data.shipments);
      setSelectedShipmentId('');
      setRiskResult(null);
    },
  });

  const selectedShipment = useMemo(
    () => shipments.find((shipment) => shipment.shipment_id === selectedShipmentId) || shipments[0],
    [shipments, selectedShipmentId]
  );

  const analyzeShipment = useMutation({
    mutationFn: (shipment: ShipmentInput) =>
      shipmentApi.runStrandsRisk(
        shipment,
        `Assess shipment ${shipment.shipment_id} from ${shipment.origin} to ${shipment.destination}.`
      ).then((res) => res.data as StrandsShipmentRiskResponse),
    onSuccess: (data) => setRiskResult(data),
  });

  const setRisks = useRiskStore((state) => state.setRisks);

  if (risks) {
    setRisks(risks);
  }

  const criticalRisks = risks?.filter((r: any) => r.severity === 'critical') || [];
  const highRisks = risks?.filter((r: any) => r.severity === 'high') || [];
  const avgConfidence =
    risks && risks.length > 0
      ? Math.round((risks.reduce((sum: number, r: any) => sum + r.confidence, 0) / risks.length) * 100)
      : 0;

  const metrics = [
    {
      label: 'Total Risks',
      value: risks?.length || 0,
      icon: Activity,
      color: 'text-primary-400',
      bgColor: 'bg-primary-500/10',
    },
    {
      label: 'Critical',
      value: criticalRisks.length,
      icon: AlertTriangle,
      color: 'text-danger-400',
      bgColor: 'bg-danger-500/10',
    },
    {
      label: 'High Priority',
      value: highRisks.length,
      icon: TrendingUp,
      color: 'text-orange-400',
      bgColor: 'bg-orange-500/10',
    },
    {
      label: 'Avg Confidence',
      value: `${avgConfidence}%`,
      icon: Clock,
      color: 'text-green-400',
      bgColor: 'bg-green-500/10',
    },
  ];

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-800 rounded w-1/4" />
          <div className="grid grid-cols-4 gap-4">
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
          <p className="text-slate-400">Shipment risk testing with Strands, XGBoost, Gemini, vessel, weather, and trade signals</p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div key={metric.label} className="card">
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

      {/* Phase 3: Shipment Tracker Widget */}
      <ShipmentTracker />

      <section className="grid grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)] gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-semibold text-white">Supplier Shipment Test Feed</h2>
              <p className="text-sm text-slate-400">
                {uploadedShipments ? 'Uploaded CSV' : 'Loaded from demo_shipments.csv'}
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
                          setRiskResult(null);
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

        <div className="card">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-semibold text-white">AI Shipment Analysis</h2>
              <p className="text-sm text-slate-400">Runs the Strands endpoint with live intelligence</p>
            </div>
            <button
              onClick={() => selectedShipment && analyzeShipment.mutate(selectedShipment)}
              disabled={!selectedShipment || analyzeShipment.isPending}
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
            >
              <Zap className="w-4 h-4" />
              {analyzeShipment.isPending ? 'Analyzing' : 'Analyze'}
            </button>
          </div>

          {selectedShipment && (
            <div className="grid grid-cols-2 gap-3 mb-5 text-sm">
              <InfoBox icon={Route} label="Route" value={`${selectedShipment.origin} to ${selectedShipment.destination}`} />
              <InfoBox icon={Radio} label="Live Position" value={`${selectedShipment.vessel_latitude}, ${selectedShipment.vessel_longitude}`} />
              <InfoBox icon={Ship} label="Vessel" value={selectedShipment.vessel_name || selectedShipment.imo_number || 'Tracker supplied'} />
              <InfoBox icon={Clock} label="ETA" value={selectedShipment.eta_date || 'Not set'} />
            </div>
          )}

          {analyzeShipment.error && (
            <div className="rounded-lg border border-danger-500 bg-danger-500/10 p-4 text-sm text-danger-400">
              Unable to analyze shipment. Confirm the backend is running on port 8000.
            </div>
          )}

          {riskResult ? (
            <RiskResultPanel result={riskResult} />
          ) : (
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-5 text-sm text-slate-400">
              Select a shipment and run analysis to test vessel telemetry, marine weather, XGBoost scoring, Gemini advice, and Strands orchestration.
            </div>
          )}
        </div>
      </section>

      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Recent Risk Assessments</h2>
        {risks && risks.length > 0 ? (
          <div className="grid grid-cols-2 gap-4">
            {risks.slice(0, 10).map((risk: any) => (
              <RiskCard key={risk.risk_id} risk={risk} />
            ))}
          </div>
        ) : (
          <div className="card text-center py-12">
            <Activity className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <p className="text-slate-400">No risks detected yet. Ingest data to begin analysis.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoBox({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
      <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <div className="text-slate-100 truncate">{value}</div>
    </div>
  );
}

function RiskResultPanel({ result }: { result: StrandsShipmentRiskResponse }) {
  const advice = result.result;
  const levelClass = {
    low: 'text-green-400 bg-green-500/10',
    medium: 'text-yellow-300 bg-yellow-500/10',
    high: 'text-orange-300 bg-orange-500/10',
    critical: 'text-danger-400 bg-danger-500/10',
  }[advice.risk_level];

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`rounded px-2 py-1 text-xs font-semibold uppercase ${levelClass}`}>
                {advice.risk_level}
              </span>
              <span className="text-xs text-slate-500">{result.orchestration_method}</span>
            </div>
            <div className="text-3xl font-bold text-white">{advice.risk_score.toFixed(2)}</div>
            <p className="text-sm text-slate-400 mt-1">{advice.decision}</p>
          </div>
          <div className="text-right text-sm">
            <div className="flex items-center gap-2 text-green-400 justify-end">
              <CheckCircle2 className="w-4 h-4" />
              {advice.confidence_score}% confidence
            </div>
            <div className="text-slate-500 mt-1">{result.agent}</div>
          </div>
        </div>
        <p className="mt-4 text-sm text-slate-300 leading-6">{advice.reason}</p>
      </div>

      {(['high', 'critical'].includes(advice.risk_level?.toLowerCase() || '')) && (
        <div className="rounded-lg border border-red-500 bg-red-500/10 p-4">
          <div className="flex items-start gap-3">
            <span className="text-xl">⚠️</span>
            <div className="flex-1">
              <h4 className="text-sm font-bold text-red-300">High Risk Detected — Resolution Package Available</h4>
              <p className="mt-1 text-xs text-red-200/70">
                AI can draft a complete resolution package for this shipment, including executive summaries and communication drafts.
              </p>
              <button
                onClick={() => window.location.href = `/shipments/${advice.shipment_id}`}
                className="mt-3 inline-flex items-center gap-2 rounded bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 px-3 py-1.5 text-xs font-semibold text-red-200 transition-colors"
              >
                View Shipment & Generate Resolution
              </button>
            </div>
          </div>
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold text-white mb-2">Recommended Actions</h3>
        <div className="space-y-2">
          {advice.recommended_actions.map((action) => (
            <div key={action} className="rounded-lg bg-slate-800/70 px-3 py-2 text-sm text-slate-300">
              {action}
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-white mb-2">Signals</h3>
        <div className="space-y-2">
          {advice.signals.length > 0 ? advice.signals.map((signal) => (
            <div key={signal} className="rounded-lg border border-slate-800 px-3 py-2 text-xs text-slate-400">
              {signal}
            </div>
          )) : (
            <div className="rounded-lg border border-slate-800 px-3 py-2 text-xs text-slate-500">
              No route-specific signals matched.
            </div>
          )}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-white mb-2">Model Features</h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {Object.entries(advice.features).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-2 rounded bg-slate-950/50 px-3 py-2">
              <span className="text-slate-500 truncate">{key}</span>
              <span className="font-mono text-slate-200">{Number(value).toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
