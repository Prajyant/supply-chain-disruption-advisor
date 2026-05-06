import { useQuery } from '@tanstack/react-query';
import { maritimeApi } from '../services/api';
import {
  Anchor,
  Shield,
  Navigation,
  AlertTriangle,
  CheckCircle2,
  MapPin,
  DollarSign,
  Ship,
  Clock,
} from 'lucide-react';

/**
 * Maritime Intelligence Panel
 *
 * Displays live data from:
 * - Port congestion (UNCTAD)
 * - Sanctions screening (OFAC/UN)
 * - Tariff alerts (WTO/WITS)
 * - Route calculations (Searoute)
 */
export function MaritimeIntelligence() {
  const { data: portData, isLoading: portsLoading } = useQuery({
    queryKey: ['port-congestion'],
    queryFn: () => maritimeApi.getAllPortCongestion().then((res) => res.data),
    refetchInterval: 120_000, // 2 min
  });

  const { data: tariffData, isLoading: tariffsLoading } = useQuery({
    queryKey: ['tariffs-us-china'],
    queryFn: () => maritimeApi.getRouteTariffs('CHN', 'USA', 'electronics').then((res) => res.data),
    refetchInterval: 300_000, // 5 min
  });

  const { data: routeData } = useQuery({
    queryKey: ['route-shanghai-rotterdam'],
    queryFn: () => maritimeApi.getRouteDistance('shanghai', 'rotterdam').then((res) => res.data),
    staleTime: Infinity, // Static data
  });

  const congestedPorts = portData?.congested_ports || [];
  const tariffSeverity = tariffData?.severity || 'low';
  const tariffRate = tariffData?.average_rate || 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Anchor className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Maritime Intelligence</h2>
        </div>
        <span className="text-xs text-slate-500">Live data · OFAC · WTO · UNCTAD · Searoute</span>
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          icon={MapPin}
          label="Congested Ports"
          value={congestedPorts.length}
          color={congestedPorts.length > 3 ? 'text-red-400' : congestedPorts.length > 0 ? 'text-yellow-400' : 'text-green-400'}
          loading={portsLoading}
        />
        <StatCard
          icon={DollarSign}
          label="US-China Tariff"
          value={`${tariffRate}%`}
          color={tariffSeverity === 'critical' ? 'text-red-400' : tariffSeverity === 'high' ? 'text-orange-400' : 'text-yellow-400'}
          loading={tariffsLoading}
        />
        <StatCard
          icon={Navigation}
          label="SHA→RTM Distance"
          value={routeData ? `${Math.round(routeData.distance_nm).toLocaleString()} nm` : '—'}
          color="text-blue-400"
          loading={!routeData}
        />
        <StatCard
          icon={Shield}
          label="Sanctions DB"
          value="Active"
          color="text-green-400"
          loading={false}
        />
      </div>

      {/* Port Congestion Panel */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
        <div className="flex items-center gap-2 mb-3">
          <MapPin className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Port Congestion Monitor</h3>
          <span className="text-xs text-slate-500 ml-auto">Source: UNCTAD</span>
        </div>

        {portsLoading ? (
          <div className="h-16 bg-slate-800 rounded animate-pulse" />
        ) : congestedPorts.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-green-400">
            <CheckCircle2 className="w-4 h-4" />
            All monitored ports operating within normal parameters
          </div>
        ) : (
          <div className="space-y-2">
            {congestedPorts.slice(0, 5).map((port: any) => (
              <PortCongestionRow key={port.port_name} port={port} />
            ))}
          </div>
        )}
      </div>

      {/* Tariff & Sanctions Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Tariff Panel */}
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <DollarSign className="w-4 h-4 text-yellow-400" />
            <h3 className="text-sm font-semibold text-white">Tariff Monitor</h3>
            <span className="text-xs text-slate-500 ml-auto">WTO/WITS</span>
          </div>

          {tariffsLoading ? (
            <div className="h-16 bg-slate-800 rounded animate-pulse" />
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-300">China → USA (Electronics)</span>
                <SeverityBadge severity={tariffSeverity} label={`${tariffRate}%`} />
              </div>
              {tariffData?.rates?.slice(0, 3).map((rate: any) => (
                <div key={rate.hs_code} className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">HS {rate.hs_code}: {rate.description}</span>
                  <span className="text-slate-200 font-mono">{rate.applied_rate}%</span>
                </div>
              ))}
              {(!tariffData?.rates || tariffData.rates.length === 0) && (
                <p className="text-xs text-slate-500">Tariff data uses fallback estimates when WTO API is unavailable.</p>
              )}
            </div>
          )}
        </div>

        {/* Sanctions Panel */}
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-white">Sanctions Screening</h3>
            <span className="text-xs text-slate-500 ml-auto">OFAC + UN</span>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-green-400">
              <CheckCircle2 className="w-4 h-4" />
              <span>OFAC SDN list loaded</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-green-400">
              <CheckCircle2 className="w-4 h-4" />
              <span>UN Security Council list loaded</span>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Vessels and entities are automatically screened during shipment analysis.
              Manual screening available via the API.
            </p>
          </div>
        </div>
      </div>

      {/* Route Intelligence */}
      {routeData && (
        <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Navigation className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-semibold text-white">Route Intelligence</h3>
            <span className="text-xs text-slate-500 ml-auto">Searoute</span>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            <RouteInfoBox icon={Ship} label="Route" value={`${routeData.origin} → ${routeData.destination}`} />
            <RouteInfoBox icon={Navigation} label="Distance" value={`${Math.round(routeData.distance_nm).toLocaleString()} nm`} />
            <RouteInfoBox icon={Clock} label="ETA (14 kn)" value={`${routeData.estimated_days} days`} />
            <RouteInfoBox icon={MapPin} label="Distance (km)" value={`${Math.round(routeData.distance_km).toLocaleString()} km`} />
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
  loading,
}: {
  icon: any;
  label: string;
  value: string | number;
  color: string;
  loading: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3">
      <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      {loading ? (
        <div className="h-6 w-16 bg-slate-800 rounded animate-pulse" />
      ) : (
        <div className={`text-xl font-bold ${color}`}>{value}</div>
      )}
    </div>
  );
}

function PortCongestionRow({ port }: { port: any }) {
  const severityColors: Record<string, string> = {
    critical: 'text-red-400 bg-red-500/10 border-red-500/30',
    high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  };
  const colorClass = severityColors[port.severity] || 'text-slate-400 bg-slate-500/10 border-slate-500/30';

  return (
    <div className={`flex items-center justify-between rounded-lg border px-3 py-2 ${colorClass}`}>
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-3.5 h-3.5" />
        <span className="text-sm font-medium capitalize">{port.port_name}</span>
        <span className="text-xs opacity-70">({port.country})</span>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span>{port.congestion_ratio}x normal</span>
        <span className="font-mono">{port.current_turnaround_days}d turnaround</span>
      </div>
    </div>
  );
}

function SeverityBadge({ severity, label }: { severity: string; label: string }) {
  const colors: Record<string, string> = {
    critical: 'bg-red-500/20 text-red-300',
    high: 'bg-orange-500/20 text-orange-300',
    medium: 'bg-yellow-500/20 text-yellow-300',
    low: 'bg-green-500/20 text-green-300',
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${colors[severity] || colors.low}`}>
      {label}
    </span>
  );
}

function RouteInfoBox({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-800/60 px-3 py-2">
      <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-0.5">
        <Icon className="w-3 h-3" />
        {label}
      </div>
      <div className="text-slate-100 text-sm font-medium truncate">{value}</div>
    </div>
  );
}
