import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { loadDemoShipments } from '../services/shipmentData';
import { useShipmentStore } from '../store/shipmentStore';
import { networkApi, maritimeApi, shipmentApi } from '../services/api';
import { MaritimeIntelligence } from '../components/MaritimeIntelligence';
import ReactFlow, { Background, Controls, useNodesState, useEdgesState } from 'reactflow';
import 'reactflow/dist/style.css';
import React from 'react';
import {
  AlertTriangle, CheckCircle2, ExternalLink, Activity,
  Anchor, MapPin, Shield, DollarSign, ChevronDown,
  Package, Loader2, TrendingUp, Zap,
} from 'lucide-react';

/* ── helpers ───────────────────────────────────────────────────────── */
function nodeAccent(status?: string) {
  const s = status?.toLowerCase() ?? '';
  if (s === 'disrupted' || s === 'critical') return '#ef4444';
  if (s === 'at_risk'   || s === 'high')     return '#f97316';
  if (s === 'degraded'  || s === 'medium')   return '#eab308';
  return '#22c55e';
}
function riskLevel(score: number): 'critical' | 'high' | 'medium' | 'low' {
  if (score >= 8) return 'critical';
  if (score >= 6) return 'high';
  if (score >= 4) return 'medium';
  return 'low';
}
const RISK_BORDER: Record<string, string> = {
  critical: 'border-red-500/35 bg-red-500/5',
  high:     'border-orange-500/35 bg-orange-500/5',
  medium:   'border-amber-500/35 bg-amber-500/5',
  low:      'border-slate-700 bg-slate-900/30',
};
const BADGE_CLS: Record<string, string> = {
  critical: 'badge-critical',
  high:     'badge-high',
  medium:   'badge-medium',
  low:      'badge-low',
};

/* ── component ─────────────────────────────────────────────────────── */
export function OperationsDashboard() {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const { data: demoShipments = [] } = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
  });
  const { uploadedShipments } = useShipmentStore();
  const shipments = uploadedShipments
    ? [...demoShipments, ...uploadedShipments.filter(u => !demoShipments.some(d => d.shipment_id === u.shipment_id))]
    : demoShipments;

  const { data: selectedAnalysis, isLoading: analysisLoading } = useQuery({
    queryKey: ['shipment-preloaded', selectedId],
    queryFn: () => shipmentApi.getPreloadedAnalysis(selectedId!).then(r => r.data),
    enabled: !!selectedId,
    retry: false,
  });

  const { data: network, isLoading: netLoading } = useQuery({
    queryKey: ['network'],
    queryFn: () => networkApi.getNetwork().then(r => r.data),
    refetchInterval: 60_000,
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  React.useEffect(() => {
    if (!network) return;
    const suppliers  = network.nodes.filter((n: any) => n.type === 'supplier');
    const warehouses = network.nodes.filter((n: any) => n.type === 'warehouse');
    const plants     = network.nodes.filter((n: any) => n.type === 'plant');
    const COL_X = { supplier: 0, warehouse: 320, plant: 640 };
    const ROW = 90;
    const maxCol = Math.max(suppliers.length, warehouses.length, plants.length);

    function col(items: any[], x: number) {
      const startY = Math.max(0, (maxCol * ROW - items.length * ROW) / 2);
      return items.map((n: any, i: number) => ({
        id: n.id,
        type: 'default',
        position: { x, y: startY + i * ROW },
        data: {
          label: (
            <div className="text-center leading-tight">
              <p className="text-[11px] font-semibold text-white truncate max-w-[130px]">{n.name}</p>
              <p className="text-[9px] text-slate-500 uppercase tracking-wide">{n.type}</p>
            </div>
          ),
        },
        style: {
          background: '#0f172a',
          border: `2px solid ${nodeAccent(n.status)}`,
          borderRadius: 10,
          padding: '8px 10px',
          width: 155,
          fontSize: 11,
          color: '#e2e8f0',
        },
      }));
    }

    setNodes([
      ...col(suppliers, COL_X.supplier),
      ...col(warehouses, COL_X.warehouse),
      ...col(plants, COL_X.plant),
    ]);
    setEdges(network.edges.map((e: any) => ({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      style: { stroke: '#334155', strokeWidth: 1.5 },
      animated: false,
    })));
  }, [network, setNodes, setEdges]);

  /* Disruptions from shipments */
  const disruptions = shipments.map((s) => {
    let score = 3.0;
    if (s.inventory_days_cover <= 5)       score += 3.0;
    else if (s.inventory_days_cover <= 10)  score += 2.0;
    else if (s.inventory_days_cover <= 15)  score += 1.0;
    if (s.supplier_delay_count >= 5)        score += 2.0;
    else if (s.supplier_delay_count >= 3)   score += 1.5;
    else if (s.supplier_delay_count >= 1)   score += 0.5;
    if (s.lead_time_days >= 30)             score += 1.5;
    else if (s.lead_time_days >= 20)        score += 1.0;
    if ((s.priority_score ?? 0) >= 8)       score += 1.0;
    if (s.declared_value_usd > 500_000)    score += 1.0;
    score = Math.min(10, Math.max(0, score));
    const level = riskLevel(score);
    return { ...s, riskScore: Math.round(score * 10) / 10, level };
  })
    .filter(d => d.level === 'critical' || d.level === 'high')
    .sort((a, b) => b.riskScore - a.riskScore)
    .slice(0, 8);

  const critCount  = disruptions.filter(d => d.level === 'critical').length;
  const healthScore = Math.max(0, Math.min(100, 100 - critCount * 15 - disruptions.length * 5));
  const healthColor = healthScore >= 75 ? 'bg-emerald-500' : healthScore >= 50 ? 'bg-amber-500' : 'bg-red-500';
  const healthText  = healthScore >= 75 ? 'text-emerald-400' : healthScore >= 50 ? 'text-amber-400' : 'text-red-400';
  const selectedShipment = shipments.find(s => s.shipment_id === selectedId);

  return (
    <div className="flex flex-col h-full bg-slate-950 overflow-hidden">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between px-8 pt-7 pb-4 shrink-0">
        <div>
          <h1 className="page-title">Operations Control Center</h1>
          <p className="page-subtitle">
            Live supply chain visibility · {shipments.length} active shipments
          </p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-semibold ${
          critCount > 0
            ? 'border-red-500/35 bg-red-500/10 text-red-300'
            : 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300'
        }`}>
          <span className={`w-2 h-2 rounded-full animate-pulse ${critCount > 0 ? 'bg-red-400' : 'bg-emerald-400'}`} />
          {critCount > 0 ? `${critCount} Critical Alert${critCount > 1 ? 's' : ''}` : 'All Systems Normal'}
        </div>
      </div>

      {/* ── Shipment selector ── */}
      <div className="px-8 pb-4 shrink-0">
        <div className="card !p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2 shrink-0">
              <Package className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-semibold text-white">Inspect Shipment</span>
            </div>
            <div className="relative flex-1 min-w-[240px] max-w-md">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="w-full flex items-center justify-between gap-2 px-4 py-2.5 rounded-lg border border-slate-700 bg-slate-800 hover:border-slate-600 transition-colors text-left text-sm"
              >
                <span className={selectedId ? 'text-white' : 'text-slate-400'}>
                  {selectedShipment
                    ? `${selectedShipment.shipment_id} — ${selectedShipment.supplier} (${selectedShipment.origin} → ${selectedShipment.destination})`
                    : 'Select a shipment to inspect…'}
                </span>
                <ChevronDown className={`w-4 h-4 text-slate-400 shrink-0 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              {dropdownOpen && (
                <div className="absolute z-50 mt-1 w-full max-h-60 overflow-y-auto rounded-xl border border-slate-700 bg-slate-800 shadow-2xl">
                  {shipments.map((s) => (
                    <button
                      key={s.shipment_id}
                      onClick={() => { setSelectedId(s.shipment_id); setDropdownOpen(false); }}
                      className={`w-full text-left px-4 py-2.5 hover:bg-slate-700/50 transition-colors border-b border-slate-700/40 last:border-0 text-sm ${
                        s.shipment_id === selectedId ? 'bg-blue-500/8 border-l-2 border-l-blue-500' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-white">{s.shipment_id}</span>
                        <span className="text-xs text-slate-500">{s.transport_mode}</span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {s.supplier} · {s.origin} → {s.destination} · {s.material}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {selectedId && (
              <button
                onClick={() => navigate(`/shipments/${selectedId}`)}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-blue-300 border border-blue-500/30 bg-blue-500/10 rounded-lg hover:bg-blue-500/20 transition-colors shrink-0"
              >
                Full Analysis <ExternalLink className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Selected shipment metrics */}
          {selectedShipment && (
            <div className="mt-4 pt-4 border-t border-slate-800">
              {analysisLoading ? (
                <div className="flex items-center gap-2 text-slate-400 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading risk analysis…
                </div>
              ) : selectedAnalysis?.result ? (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  <OpsKpi label="Risk Score" value={`${selectedAnalysis.result.risk_score}/10`}
                    color={riskLevel(selectedAnalysis.result.risk_score) === 'critical' ? 'text-red-400' : riskLevel(selectedAnalysis.result.risk_score) === 'high' ? 'text-orange-400' : 'text-amber-400'} />
                  <OpsKpi label="Risk Level" value={selectedAnalysis.result.risk_level?.toUpperCase()}
                    color={riskLevel(selectedAnalysis.result.risk_score) === 'critical' ? 'text-red-400' : 'text-orange-400'} />
                  <OpsKpi label="Inventory Cover" value={`${selectedShipment.inventory_days_cover}d`}
                    color={selectedShipment.inventory_days_cover <= 7 ? 'text-red-400' : selectedShipment.inventory_days_cover <= 14 ? 'text-amber-400' : 'text-emerald-400'} />
                  <OpsKpi label="Lead Time" value={`${selectedShipment.lead_time_days}d`}
                    color={selectedShipment.lead_time_days >= 30 ? 'text-orange-400' : 'text-slate-200'} />
                  <OpsKpi label="Supplier Delays" value={String(selectedShipment.supplier_delay_count)}
                    color={selectedShipment.supplier_delay_count >= 3 ? 'text-orange-400' : 'text-slate-200'} />
                  <OpsKpi label="Value" value={`$${(selectedShipment.declared_value_usd / 1000).toFixed(0)}K`} color="text-slate-200" />
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  <OpsKpi label="Inventory Cover" value={`${selectedShipment.inventory_days_cover}d`}
                    color={selectedShipment.inventory_days_cover <= 7 ? 'text-red-400' : 'text-slate-200'} />
                  <OpsKpi label="Lead Time"       value={`${selectedShipment.lead_time_days}d`}   color="text-slate-200" />
                  <OpsKpi label="Supplier Delays" value={String(selectedShipment.supplier_delay_count)} color="text-slate-200" />
                  <OpsKpi label="Quantity"        value={String(selectedShipment.quantity)}        color="text-slate-200" />
                  <OpsKpi label="Value"           value={`$${(selectedShipment.declared_value_usd / 1000).toFixed(0)}K`} color="text-slate-200" />
                  <OpsKpi label="Mode"            value={selectedShipment.transport_mode}          color="text-slate-200" />
                </div>
              )}

              {selectedAnalysis?.result?.signals?.length > 0 && (
                <div className="mt-3 p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
                  <p className="text-[10px] font-semibold text-amber-400 uppercase tracking-wide mb-2">Risk Signals</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedAnalysis.result.signals.map((sig: string, i: number) => (
                      <span key={i} className="badge bg-amber-500/10 text-amber-300 border border-amber-500/20">{sig}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Main split: graph + disruptions ── */}
      <div className="flex flex-1 min-h-0 gap-4 px-8 pb-4">

        {/* Digital twin graph */}
        <div className="flex-1 rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden flex flex-col">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
            <h2 className="section-title flex items-center gap-2">
              <Activity className="w-4 h-4 text-slate-400" />
              Digital Twin Network
            </h2>
            <span className="text-xs text-slate-600">Supplier → Warehouse → Plant</span>
          </div>
          <div className="flex-1">
            {netLoading ? (
              <div className="h-full flex items-center justify-center text-slate-600 text-sm">
                <Loader2 className="w-4 h-4 animate-spin mr-2" /> Loading network…
              </div>
            ) : (
              <ReactFlow
                nodes={nodes} edges={edges}
                onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
                fitView attributionPosition="bottom-right"
              >
                <Background color="#1e293b" gap={24} />
                <Controls showInteractive={false} />
              </ReactFlow>
            )}
          </div>
        </div>

        {/* Active disruptions */}
        <div className="w-80 shrink-0 flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-3 shrink-0">
            <h2 className="section-title flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              Active Disruptions
            </h2>
            <span className="text-xs text-slate-500">{disruptions.length} high/critical</span>
          </div>
          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {disruptions.length === 0 ? (
              <div className="empty-state h-full justify-center">
                <CheckCircle2 className="empty-state-icon text-emerald-700" />
                <p className="empty-state-title">No active disruptions</p>
              </div>
            ) : disruptions.map((d) => (
              <div
                key={d.shipment_id}
                className={`rounded-xl border p-4 transition-all duration-150 hover-lift ${RISK_BORDER[d.level]} ${
                  d.shipment_id === selectedId ? 'ring-2 ring-blue-500/40' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={`badge ${BADGE_CLS[d.level]}`}>{d.level}</span>
                      <span className="mono">{d.shipment_id}</span>
                    </div>
                    <p className="text-sm font-semibold text-white truncate">{d.supplier}</p>
                    <p className="text-xs text-slate-500">{d.origin} → {d.destination}</p>
                  </div>
                  <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${d.level === 'critical' ? 'text-red-400' : 'text-orange-400'}`} />
                </div>

                <div className="grid grid-cols-3 gap-1.5 mb-3">
                  <MiniStat label="Material"  value={d.material} />
                  <MiniStat label="Inventory" value={`${d.inventory_days_cover}d`} />
                  <MiniStat label="Delays"    value={`${d.supplier_delay_count}×`} />
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold tabular-nums text-slate-400">
                    Score: {d.riskScore}
                  </span>
                  <button
                    onClick={() => navigate(`/shipments/${d.shipment_id}`)}
                    className="flex items-center gap-1 text-xs text-slate-300 hover:text-white border border-slate-700 hover:border-slate-500 px-2.5 py-1 rounded-lg transition-colors"
                  >
                    Details <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Maritime strip ── */}
      <div className="px-8 pb-3 shrink-0">
        <MaritimeStrip origin={selectedShipment?.origin} destination={selectedShipment?.destination} />
      </div>

      {/* ── Maritime intelligence panel ── */}
      <div className="px-8 pb-4 shrink-0">
        <div className="card">
          <MaritimeIntelligence
            selectedOrigin={selectedShipment?.origin ?? null}
            selectedDestination={selectedShipment?.destination ?? null}
            selectedVesselImo={selectedShipment?.imo_number ?? null}
            selectedVesselName={selectedShipment?.vessel_name ?? null}
          />
        </div>
      </div>

      {/* ── Supply chain health bar ── */}
      <div className="px-8 pb-7 shrink-0">
        <div className="card !py-4 flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="shrink-0">
            <p className="section-title flex items-center gap-2">
              <TrendingUp className={`w-4 h-4 ${healthText}`} />
              Supply Chain Health
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              {shipments.length} active shipments · {critCount} critical alert{critCount !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex-1 flex items-center gap-4">
            <div className="flex-1 h-2.5 bg-slate-800 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-700 ${healthColor}`}
                   style={{ width: `${healthScore}%` }} />
            </div>
            <span className={`text-xl font-bold tabular-nums shrink-0 ${healthText}`}>
              {healthScore}/100
            </span>
          </div>
        </div>
      </div>

    </div>
  );
}

/* ── sub-components ── */
function OpsKpi({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl px-3 py-2">
      <p className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</p>
      <p className={`text-sm font-bold mt-0.5 ${color}`}>{value}</p>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-800/60 rounded-lg px-2 py-1.5">
      <p className="text-[9px] text-slate-600 uppercase tracking-wide">{label}</p>
      <p className="text-xs font-semibold text-slate-200 truncate">{value}</p>
    </div>
  );
}

function MaritimeStrip({ origin, destination }: { origin?: string | null; destination?: string | null }) {
  const hasSelection = !!(origin && destination);
  const { data: portData } = useQuery({
    queryKey: ['port-congestion'],
    queryFn: () => maritimeApi.getAllPortCongestion().then(r => r.data),
    refetchInterval: 120_000,
    enabled: !hasSelection,
  });
  const { data: originPort } = useQuery({
    queryKey: ['port-strip-origin', origin],
    queryFn: () => maritimeApi.getPortCongestion(origin!).then(r => r.data),
    enabled: !!origin,
    refetchInterval: 120_000,
  });
  const { data: destPort } = useQuery({
    queryKey: ['port-strip-dest', destination],
    queryFn: () => maritimeApi.getPortCongestion(destination!).then(r => r.data),
    enabled: !!destination,
    refetchInterval: 120_000,
  });
  const { data: tariff } = useQuery({
    queryKey: ['tariffs-strip'],
    queryFn: () => maritimeApi.getRouteTariffs('CHN', 'USA', 'electronics').then(r => r.data),
    refetchInterval: 300_000,
  });

  const congested = hasSelection
    ? [originPort?.congestion_ratio > 1.2 && { port_name: origin, congestion_ratio: originPort.congestion_ratio },
       destPort?.congestion_ratio > 1.2 && { port_name: destination, congestion_ratio: destPort.congestion_ratio }].filter(Boolean)
    : (portData?.congested_ports || []);

  const tariffRate     = tariff?.average_rate || 0;
  const tariffSeverity = tariff?.severity || 'low';
  const tColor: Record<string, string> = { critical: 'text-red-400', high: 'text-orange-400', medium: 'text-amber-400', low: 'text-emerald-400' };

  return (
    <div className="card !py-3 flex items-center gap-6 overflow-x-auto">
      <div className="flex items-center gap-2 shrink-0">
        <Anchor className="w-3.5 h-3.5 text-blue-400" />
        <span className="text-xs font-bold text-white uppercase tracking-wide">Maritime Intel</span>
      </div>
      <div className="divider-v h-5" />
      <div className="flex items-center gap-2 shrink-0">
        <MapPin className="w-3.5 h-3.5 text-orange-400" />
        <span className="text-xs text-slate-400">Congested:</span>
        <span className={`text-xs font-bold ${congested.length > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
          {congested.length > 0 ? `${congested.length} port${congested.length > 1 ? 's' : ''}` : 'Clear'}
        </span>
      </div>
      <div className="divider-v h-5" />
      <div className="flex items-center gap-2 shrink-0">
        <DollarSign className="w-3.5 h-3.5 text-amber-400" />
        <span className="text-xs text-slate-400">CN→US Tariff:</span>
        <span className={`text-xs font-bold ${tColor[tariffSeverity]}`}>{tariffRate}%</span>
      </div>
      <div className="divider-v h-5" />
      <div className="flex items-center gap-2 shrink-0">
        <Shield className="w-3.5 h-3.5 text-emerald-400" />
        <span className="text-xs text-slate-400">Sanctions:</span>
        <span className="text-xs font-bold text-emerald-400">OFAC + UN Active</span>
      </div>
    </div>
  );
}
