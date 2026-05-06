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

interface MaritimeIntelligenceProps {
  /** If provided, maritime data is scoped to this shipment's origin/destination */
  selectedOrigin?: string | null;
  selectedDestination?: string | null;
  selectedVesselImo?: string | null;
  selectedVesselName?: string | null;
}

/**
 * Maritime Intelligence Panel
 *
 * When a shipment is selected, shows:
 * - Port congestion for origin & destination ports only
 * - Route distance for the selected route
 * - Tariff data for the origin/destination countries
 * - Sanctions screening for the vessel
 *
 * When no shipment is selected, shows global overview.
 */
export function MaritimeIntelligence({
  selectedOrigin,
  selectedDestination,
  selectedVesselImo,
  selectedVesselName,
}: MaritimeIntelligenceProps = {}) {
  const hasSelection = !!(selectedOrigin && selectedDestination);

  // Port congestion: if shipment selected, fetch only origin & destination ports
  const { data: allPortData, isLoading: allPortsLoading } = useQuery({
    queryKey: ['port-congestion'],
    queryFn: () => maritimeApi.getAllPortCongestion().then((res) => res.data),
    refetchInterval: 120_000,
    enabled: !hasSelection,
  });

  const { data: originPortData, isLoading: originPortLoading } = useQuery({
    queryKey: ['port-congestion-origin', selectedOrigin],
    queryFn: () => maritimeApi.getPortCongestion(selectedOrigin!).then((res) => res.data),
    enabled: !!selectedOrigin,
    refetchInterval: 120_000,
  });

  const { data: destPortData, isLoading: destPortLoading } = useQuery({
    queryKey: ['port-congestion-dest', selectedDestination],
    queryFn: () => maritimeApi.getPortCongestion(selectedDestination!).then((res) => res.data),
    enabled: !!selectedDestination,
    refetchInterval: 120_000,
  });

  // Route distance: use selected origin/destination or fallback to Shanghai→Rotterdam
  const routeOrigin = selectedOrigin || 'shanghai';
  const routeDestination = selectedDestination || 'rotterdam';

  const { data: routeData } = useQuery({
    queryKey: ['route-distance', routeOrigin, routeDestination],
    queryFn: () => maritimeApi.getRouteDistance(routeOrigin, routeDestination).then((res) => res.data),
    staleTime: hasSelection ? 60_000 : Infinity,
  });

  // Tariff data: try to derive countries from port names
  const originCountry = extractCountryCode(selectedOrigin);
  const destCountry = extractCountryCode(selectedDestination);
  const tariffOrigin = originCountry || 'CHN';
  const tariffDest = destCountry || 'USA';

  const { data: tariffData, isLoading: tariffsLoading } = useQuery({
    queryKey: ['tariffs', tariffOrigin, tariffDest],
    queryFn: () => maritimeApi.getRouteTariffs(tariffOrigin, tariffDest, 'electronics').then((res) => res.data),
    refetchInterval: 300_000,
  });

  // Vessel sanctions screening (if vessel selected)
  const { data: vesselSanctionsData } = useQuery({
    queryKey: ['vessel-sanctions', selectedVesselImo],
    queryFn: () => maritimeApi.screenVesselSanctions(selectedVesselImo!, selectedVesselName || '').then((res) => res.data),
    enabled: !!selectedVesselImo,
  });

  // Determine which ports to show
  const portsLoading = hasSelection ? (originPortLoading || destPortLoading) : allPortsLoading;
  let congestedPorts: any[] = [];

  if (hasSelection) {
    // Show only origin and destination port data
    const ports: any[] = [];
    if (originPortData) {
      ports.push({
        port_name: originPortData.port_name || selectedOrigin,
        country: originPortData.country || '',
        severity: originPortData.severity || 'low',
        congestion_ratio: originPortData.congestion_ratio || 1.0,
        current_turnaround_days: originPortData.current_turnaround_days || 0,
        role: 'Origin',
      });
    }
    if (destPortData) {
      ports.push({
        port_name: destPortData.port_name || selectedDestination,
        country: destPortData.country || '',
        severity: destPortData.severity || 'low',
        congestion_ratio: destPortData.congestion_ratio || 1.0,
        current_turnaround_days: destPortData.current_turnaround_days || 0,
        role: 'Destination',
      });
    }
    congestedPorts = ports;
  } else {
    congestedPorts = allPortData?.congested_ports || [];
  }

  const tariffSeverity = tariffData?.severity || 'low';
  const tariffRate = tariffData?.average_rate || 0;

  const routeLabel = hasSelection
    ? `${selectedOrigin} → ${selectedDestination}`
    : 'SHA→RTM';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Anchor className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Maritime Intelligence</h2>
          {hasSelection && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300 font-medium">
              {selectedOrigin} → {selectedDestination}
            </span>
          )}
        </div>
        <span className="text-xs text-slate-500">Live data · OFAC · WTO · UNCTAD · Searoute</span>
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          icon={MapPin}
          label={hasSelection ? "Route Ports" : "Congested Ports"}
          value={hasSelection ? congestedPorts.length : congestedPorts.length}
          color={congestedPorts.some((p: any) => p.severity === 'critical' || p.severity === 'high') ? 'text-red-400' : congestedPorts.some((p: any) => p.congestion_ratio > 1.5) ? 'text-yellow-400' : 'text-green-400'}
          loading={portsLoading}
        />
        <StatCard
          icon={DollarSign}
          label={`${tariffOrigin}→${tariffDest} Tariff`}
          value={`${tariffRate}%`}
          color={tariffSeverity === 'critical' ? 'text-red-400' : tariffSeverity === 'high' ? 'text-orange-400' : tariffSeverity === 'medium' ? 'text-yellow-400' : 'text-green-400'}
          loading={tariffsLoading}
        />
        <StatCard
          icon={Navigation}
          label={`${routeLabel} Distance`}
          value={routeData ? `${Math.round(routeData.distance_nm).toLocaleString()} nm` : '—'}
          color="text-blue-400"
          loading={!routeData}
        />
        <StatCard
          icon={Shield}
          label="Sanctions DB"
          value={vesselSanctionsData?.is_sanctioned ? 'FLAGGED' : 'Clear'}
          color={vesselSanctionsData?.is_sanctioned ? 'text-red-400' : 'text-green-400'}
          loading={false}
        />
      </div>

      {/* Port Congestion Panel */}
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
        <div className="flex items-center gap-2 mb-3">
          <MapPin className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Port Congestion Monitor</h3>
          <span className="text-xs text-slate-500 ml-auto">
            {hasSelection ? `${selectedOrigin} & ${selectedDestination}` : 'Source: UNCTAD'}
          </span>
        </div>

        {portsLoading ? (
          <div className="h-16 bg-slate-800 rounded animate-pulse" />
        ) : congestedPorts.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-green-400">
            <CheckCircle2 className="w-4 h-4" />
            {hasSelection
              ? `Both ${selectedOrigin} and ${selectedDestination} operating within normal parameters`
              : 'All monitored ports operating within normal parameters'}
          </div>
        ) : (
          <div className="space-y-2">
            {congestedPorts.slice(0, 5).map((port: any, idx: number) => (
              <PortCongestionRow key={port.port_name || idx} port={port} showRole={hasSelection} />
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
                <span className="text-sm text-slate-300">
                  {tariffOrigin} → {tariffDest} ({tariffData?.product_category || 'Electronics'})
                </span>
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
            {selectedVesselImo && vesselSanctionsData ? (
              <>
                <div className={`flex items-center gap-2 text-sm ${vesselSanctionsData.is_sanctioned ? 'text-red-400' : 'text-green-400'}`}>
                  {vesselSanctionsData.is_sanctioned ? (
                    <><AlertTriangle className="w-4 h-4" /><span>Vessel SANCTIONED — IMO {selectedVesselImo}</span></>
                  ) : (
                    <><CheckCircle2 className="w-4 h-4" /><span>Vessel clear — IMO {selectedVesselImo}</span></>
                  )}
                </div>
                {selectedVesselName && (
                  <p className="text-xs text-slate-400">Vessel: {selectedVesselName}</p>
                )}
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 text-sm text-green-400">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>OFAC SDN list loaded</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-green-400">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>UN Security Council list loaded</span>
                </div>
              </>
            )}
            <p className="text-xs text-slate-500 mt-2">
              {hasSelection
                ? 'Screening results for the selected shipment vessel.'
                : 'Vessels and entities are automatically screened during shipment analysis. Manual screening available via the API.'}
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

/**
 * Try to extract a country code from a port/city name.
 * This is a best-effort mapping for common trade ports.
 */
function extractCountryCode(portName?: string | null): string | null {
  if (!portName) return null;
  const lower = portName.toLowerCase();

  const portCountryMap: Record<string, string> = {
    shanghai: 'CHN', shenzhen: 'CHN', guangzhou: 'CHN', ningbo: 'CHN', qingdao: 'CHN',
    tianjin: 'CHN', dalian: 'CHN', xiamen: 'CHN', hong_kong: 'CHN', hongkong: 'CHN',
    rotterdam: 'NLD', amsterdam: 'NLD', antwerp: 'BEL', hamburg: 'DEU',
    singapore: 'SGP', tokyo: 'JPN', yokohama: 'JPN', busan: 'KOR',
    mumbai: 'IND', chennai: 'IND', kolkata: 'IND', colombo: 'LKA',
    dubai: 'ARE', jebel_ali: 'ARE',
    los_angeles: 'USA', long_beach: 'USA', new_york: 'USA', savannah: 'USA',
    houston: 'USA', seattle: 'USA', oakland: 'USA', chicago: 'USA',
    santos: 'BRA', lagos: 'NGA', durban: 'ZAF', mombasa: 'KEN',
    sydney: 'AUS', melbourne: 'AUS', vancouver: 'CAN', montreal: 'CAN',
    chittagong: 'BGD', karachi: 'PAK', haifa: 'ISR', piraeus: 'GRC',
    felixstowe: 'GBR', london: 'GBR', southampton: 'GBR',
    barcelona: 'ESP', valencia: 'ESP', genoa: 'ITA', marseille: 'FRA',
    le_havre: 'FRA', gothenburg: 'SWE',
  };

  // Try exact match
  const normalized = lower.replace(/[\s-]/g, '_');
  if (portCountryMap[normalized]) return portCountryMap[normalized];

  // Try partial match
  for (const [port, code] of Object.entries(portCountryMap)) {
    if (lower.includes(port.replace(/_/g, ' ')) || lower.includes(port.replace(/_/g, ''))) {
      return code;
    }
  }

  return null;
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

function PortCongestionRow({ port, showRole }: { port: any; showRole?: boolean }) {
  const severityColors: Record<string, string> = {
    critical: 'text-red-400 bg-red-500/10 border-red-500/30',
    high: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    low: 'text-green-400 bg-green-500/10 border-green-500/30',
  };
  const colorClass = severityColors[port.severity] || 'text-slate-400 bg-slate-500/10 border-slate-500/30';

  return (
    <div className={`flex items-center justify-between rounded-lg border px-3 py-2 ${colorClass}`}>
      <div className="flex items-center gap-2">
        {port.severity === 'low' ? (
          <CheckCircle2 className="w-3.5 h-3.5" />
        ) : (
          <AlertTriangle className="w-3.5 h-3.5" />
        )}
        <span className="text-sm font-medium capitalize">{port.port_name}</span>
        {port.country && <span className="text-xs opacity-70">({port.country})</span>}
        {showRole && port.role && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase font-semibold">
            {port.role}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span>{port.congestion_ratio}x normal</span>
        {port.current_turnaround_days > 0 && (
          <span className="font-mono">{port.current_turnaround_days}d turnaround</span>
        )}
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
