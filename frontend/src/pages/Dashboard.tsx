import { useQuery } from '@tanstack/react-query';
import { riskApi } from '../services/api';
import { useRiskStore } from '../store/riskStore';
import { RiskCard } from '../components/RiskCard';
import { ShipmentTracker } from '../components/ShipmentTracker';
import {
  AlertTriangle,
  TrendingUp,
  Activity,
  Clock,
  RefreshCw,
} from 'lucide-react';

export function Dashboard() {
  const { data: risks, isLoading, error, refetch } = useQuery({
    queryKey: ['risks'],
    queryFn: () => riskApi.getRisks().then((res) => res.data),
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
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400">Real-time supply chain risk intelligence</p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-4 gap-4 mb-8">
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

      {/* Risks + Shipments Grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Recent Risks — 2 cols */}
        <div className="col-span-2">
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

        {/* Shipment Tracker Widget — 1 col */}
        <div className="col-span-1">
          <ShipmentTracker />
        </div>
      </div>
    </div>
  );
}
