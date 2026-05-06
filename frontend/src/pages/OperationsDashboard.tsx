import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { loadDemoShipments } from '../services/shipmentData';
import { useShipmentStore } from '../store/shipmentStore';
import { networkApi, maritimeApi, shipmentApi } from '../services/api';
import { MaritimeIntelligence } from '../components/MaritimeIntelligence';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import React from 'react';
import { AlertTriangle, CheckCircle2, ExternalLink, Activity, Anchor, MapPin, Shield, DollarSign, ChevronDown, Package, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// Re-use node styling from DigitalTwin
function accentColor(status?: string): string {
  const s = status?.toLowerCase() ?? '';
  if (s === 'disrupted' || s === 'critical') return '#ef4444';
  if (s === 'at_risk' || s === 'high') return '#f97316';
  if (s === 'degraded' || s === 'medium') return '#eab308';
  return '#22c55e';
}

function nodeLabel(node: any): string {
  return `${node.name}\n${node.type.toUpperCase()}`;
}

function healthColor(score: number) {
  if (score >= 75) return { bar: 'bg-green-500',  text: 'text-green-400'  };
  if (score >= 50) return { bar: 'bg-yellow-500', text: 'text-yellow-400' };
  return               { bar: 'bg-red-500',    text: 'text-red-400'    };
}

function riskLevelFromScore(score: number): 'critical' | 'high' | 'medium' | 'low' {
  if (score >= 8) return 'critical';
  if (score >= 6) return 'high';
  if (score >= 4) return 'medium';
  return 'low';
}

export function OperationsDashboard() {
  const navigate = useNavigate();
  const [selectedShipmentId, setSelectedShipmentId] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const { data: demoShipments = [] } = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
  });

  const { uploadedShipments } = useShipmentStore();
  const shipments = uploadedShipments
    ? [...demoShipments, ...uploadedShipments.filter(u => !demoShipments.some(d => d.shipment_id === u.shipment_id))]
    : demoShipments;

  // Fetch preloaded risk analysis for selected shipment
  const { data: selectedAnalysis, isLoading: analysisLoading } = useQuery({
    queryKey: ['shipment-preloaded', selectedShipmentId],
    queryFn: () => shipmentApi.getPreloadedAnalysis(selectedShipmentId!).then(res => res.data),
    enabled: !!selectedShipmentId,
    retry: false,
  });

  const { data: network, isLoading: netLoading } = useQuery({
    queryKey: ['network'],
    queryFn: () => networkApi.getNetwork().then((res) => res.data),
    refetchInterval: 60_000,
  });

  // ── Build nodes/edges from network ──────────────────────────────────────
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  React.useEffect(() => {
    if (!network) return;
    const suppliers  = network.nodes.filter((n: any) => n.type === 'supplier');
    const warehouses = network.nodes.filter((n: any) => n.type === 'warehouse');
    const plants     = network.nodes.filter((n: any) => n.type === 'plant');
    const COL_X = { supplier: 0, warehouse: 320, plant: 640 };
    const ROW_SPACING = 90;
    const maxCol = Math.max(suppliers.length, warehouses.length, plants.length);

    function layoutCol(items: any[], x: number) {
      const total = items.length * ROW_SPACING;
      const startY = Math.max(0, (maxCol * ROW_SPACING - total) / 2);
      return items.map((node: any, i: number) => ({
        id: node.id,
        type: 'default',
        position: { x, y: startY + i * ROW_SPACING },
        data: { label: nodeLabel(node), ...node },
        style: {
          background: '#0f172a',
          border: `2px solid ${accentColor(node.status)}`,
          borderRadius: '8px',
          padding: '8px',
          width: 150,
          fontSize: 11,
          color: '#e2e8f0',
        },
      }));
    }

    setNodes([
      ...layoutCol(suppliers, COL_X.supplier),
      ...layoutCol(warehouses, COL_X.warehouse),
      ...layoutCol(plants, COL_X.plant),
    ]);

    setEdges(network.edges.map((e: any) => ({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      style: { stroke: '#334155', strokeWidth: 1.5 },
      animated: false,
    })));
  }, [network, setNodes, setEdges]);

  // ── Derive disruptions from shipments using real data ──────────────────
  const disruptions = shipments
    .map((s) => {
      // Use real data: calculate risk based on actual shipment attributes
      let riskScore = 3.0;

      // Inventory pressure: low cover = high risk
      if (s.inventory_days_cover <= 5) riskScore += 3.0;
      else if (s.inventory_days_cover <= 10) riskScore += 2.0;
      else if (s.inventory_days_cover <= 15) riskScore += 1.0;

      // Supplier reliability: past delays increase risk
      if (s.supplier_delay_count >= 5) riskScore += 2.0;
      else if (s.supplier_delay_count >= 3) riskScore += 1.5;
      else if (s.supplier_delay_count >= 1) riskScore += 0.5;

      // Lead time: longer = more exposure
      if (s.lead_time_days >= 30) riskScore += 1.5;
      else if (s.lead_time_days >= 20) riskScore += 1.0;
      else if (s.lead_time_days >= 14) riskScore += 0.5;

      // Priority: high priority items are more critical
      const priority = s.priority_score ?? 0;
      if (priority >= 8) riskScore += 1.0;
      else if (priority >= 5) riskScore += 0.5;

      // Value at risk
      if (s.declared_value_usd > 500000) riskScore += 1.0;
      else if (s.declared_value_usd > 100000) riskScore += 0.5;

      riskScore = Math.min(10, Math.max(0, riskScore));
      const level = riskLevelFromScore(riskScore);
      const inventoryDays = s.inventory_days_cover ?? 14;
      const haltDate = new Date();
      haltDate.setDate(haltDate.getDate() + Math.max(1, inventoryDays));
      const hasPackage = level === 'critical' || level === 'high';
      return { ...s, riskScore: Math.round(riskScore * 10) / 10, level, haltDate, hasPackage };
    })
    .filter(d => d.level === 'critical' || d.level === 'high')
    .sort((a, b) => b.riskScore - a.riskScore)
    .slice(0, 6);

  // ── Health score ────────────────────────────────────────────────────────
  const criticalCount = disruptions.filter(d => d.level === 'critical').length;
  const healthScore = Math.max(0, Math.min(100, 100 - criticalCount * 15 - disruptions.length * 5));
  const { bar: healthBar, text: healthText } = healthColor(healthScore);

  const RISK_COLORS: Record<string, string> = {
    critical: 'border-red-500/40 bg-red-500/5',
    high:     'border-orange-500/40 bg-orange-500/5',
    medium:   'border-yellow-500/40 bg-yellow-500/5',
  };
  const PILL: Record<string, string> = {
    critical: 'bg-red-500/20 text-red-300',
    high:     'bg-orange-500/20 text-orange-300',
    medium:   'bg-yellow-500/20 text-yellow-300',
  };

  const selectedShipment = shipments.find(s => s.shipment_id === selectedShipmentId);

  return (
    <div className="flex flex-col h-full bg-slate-950">

      {/* Header */}
      <div className="flex items-center justify-between px-8 pt-8 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Operations Control Center</h1>
          <p className="text-slate-400 text-sm mt-0.5">Live supply chain visibility · {shipments.length} active shipments</p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${criticalCount > 0 ? 'border-red-500/40 bg-red-500/10 text-red-300' : 'border-green-500/40 bg-green-500/10 text-green-300'}`}>
          <span className={`w-2 h-2 rounded-full animate-pulse ${criticalCount > 0 ? 'bg-red-400' : 'bg-green-400'}`} />
          <span className="text-xs font-semibold">{criticalCount > 0 ? `${criticalCount} Critical Alert${criticalCount > 1 ? 's' : ''}` : 'All Systems Normal'}</span>
        </div>
      </div>

      {/* ── Shipment Selector ── */}
      <div className="px-8 pb-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-semibold text-white">Inspect Shipment</span>
            </div>
            <div className="relative flex-1 max-w-md">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="w-full flex items-center justify-between gap-2 px-4 py-2.5 rounded-lg border border-slate-700 bg-slate-800 hover:border-slate-600 transition-colors text-left"
              >
                <span className={`text-sm ${selectedShipmentId ? 'text-white' : 'text-slate-400'}`}>
                  {selectedShipment
                    ? `${selectedShipment.shipment_id} — ${selectedShipment.supplier} (${selectedShipment.origin} → ${selectedShipment.destination})`
                    : 'Select a shipment to inspect...'}
                </span>
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              {dropdownOpen && (
                <div className="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-lg border border-slate-700 bg-slate-800 shadow-xl">
                  {shipments.map((s) => (
                    <button
                      key={s.shipment_id}
                      onClick={() => { setSelectedShipmentId(s.shipment_id); setDropdownOpen(false); }}
                      className={`w-full text-left px-4 py-2.5 hover:bg-slate-700/50 transition-colors border-b border-slate-700/50 last:border-0 ${
                        s.shipment_id === selectedShipmentId ? 'bg-blue-500/10 border-l-2 border-l-blue-500' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-white">{s.shipment_id}</span>
                        <span className="text-xs text-slate-500">{s.transport_mode}</span>
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        {s.supplier} · {s.origin} → {s.destination} · {s.material}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {selectedShipmentId && (
              <button
                onClick={() => navigate(`/shipments/${selectedShipmentId}`)}
                className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-blue-300 border border-blue-500/30 bg-blue-500/10 rounded-lg hover:bg-blue-500/20 transition-colors"
              >
                Full Analysis <ExternalLink className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Selected Shipment Details */}
          {selectedShipment && (
            <div className="mt-4 pt-4 border-t border-slate-800">
              {analysisLoading ? (
                <div className="flex items-center gap-2 text-slate-400 text-sm py-4">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading risk analysis...
                </div>
              ) : selectedAnalysis?.result ? (
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  <MetricCard label="Risk Score" value={`${selectedAnalysis.result.risk_score}/10`} color={riskLevelFromScore(selectedAnalysis.result.risk_score)} />
                  <MetricCard label="Risk Level" value={selectedAnalysis.result.risk_level?.toUpperCase()} color={riskLevelFromScore(selectedAnalysis.result.risk_score)} />
                  <MetricCard label="Inventory Cover" value={`${selectedShipment.inventory_days_cover}d`} color={selectedShipment.inventory_days_cover <= 7 ? 'critical' : selectedShipment.inventory_days_cover <= 14 ? 'medium' : 'low'} />
                  <MetricCard label="Lead Time" value={`${selectedShipment.lead_time_days}d`} color={selectedShipment.lead_time_days >= 30 ? 'high' : 'low'} />
                  <MetricCard label="Supplier Delays" value={String(selectedShipment.supplier_delay_count)} color={selectedShipment.supplier_delay_count >= 3 ? 'high' : 'low'} />
                  <MetricCard label="Value" value={`$${(selectedShipment.declared_value_usd / 1000).toFixed(0)}K`} color="low" />
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  <MetricCard label="Inventory Cover" value={`${selectedShipment.inventory_days_cover}d`} color={selectedShipment.inventory_days_cover <= 7 ? 'critical' : selectedShipment.inventory_days_cover <= 14 ? 'medium' : 'low'} />
                  <MetricCard label="Lead Time" value={`${selectedShipment.lead_time_days}d`} color={selectedShipment.lead_time_days >= 30 ? 'high' : 'low'} />
                  <MetricCard label="Supplier Delays" value={String(selectedShipment.supplier_delay_count)} color={selectedShipment.supplier_delay_count >= 3 ? 'high' : 'low'} />
                  <MetricCard label="Quantity" value={String(selectedShipment.quantity)} color="low" />
                  <MetricCard label="Value" value={`$${(selectedShipment.declared_value_usd / 1000).toFixed(0)}K`} color="low" />
                  <MetricCard label="Transport" value={selectedShipment.transport_mode} color="low" />
                </div>
              )}

              {/* Signals from preloaded analysis */}
              {selectedAnalysis?.result?.signals && selectedAnalysis.result.signals.length > 0 && (
                <div className="mt-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/50">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Risk Signals</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedAnalysis.result.signals.map((signal: string, i: number) => (
                      <span key={i} className="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                        {signal}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main split layout */}
      <div className="flex flex-1 min-h-0 gap-0 px-8 pb-4">

        {/* Left: Digital Twin graph */}
        <div className="w-[60%] rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden flex flex-col mr-4">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">Digital Twin Network</h2>
            <span className="text-xs text-slate-500">Supplier → Warehouse → Plant</span>
          </div>
          <div className="flex-1">
            {netLoading ? (
              <div className="h-full flex items-center justify-center text-slate-500 text-sm">Loading network…</div>
            ) : (
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                fitView
                attributionPosition="bottom-right"
              >
                <Background color="#1e293b" gap={24} />
                <Controls showInteractive={false} />
              </ReactFlow>
            )}
          </div>
        </div>

        {/* Right: Active Disruptions */}
        <div className="w-[40%] flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Active Disruptions</h2>
            <span className="text-xs text-slate-500">{disruptions.length} high/critical</span>
          </div>
          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {disruptions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-600 gap-3">
                <CheckCircle2 className="w-10 h-10" />
                <p className="text-sm">No active disruptions detected</p>
              </div>
            ) : (
              disruptions.map((d) => (
                <div
                  key={d.shipment_id}
                  className={`rounded-lg border p-4 ${RISK_COLORS[d.level]} ${d.shipment_id === selectedShipmentId ? 'ring-2 ring-blue-500/50' : ''}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded uppercase ${PILL[d.level]}`}>
                          {d.level}
                        </span>
                        <span className="text-xs font-mono text-slate-400">{d.shipment_id}</span>
                        <span className="text-xs text-slate-500">Score: {d.riskScore}</span>
                      </div>
                      <p className="text-sm font-semibold text-white mt-1 truncate">{d.supplier}</p>
                      <p className="text-xs text-slate-400">{d.origin} → {d.destination}</p>
                    </div>
                    <AlertTriangle className={`w-5 h-5 shrink-0 mt-0.5 ${d.level === 'critical' ? 'text-red-400' : 'text-orange-400'}`} />
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-xs mt-3">
                    <div className="bg-slate-800/60 rounded px-2 py-1.5">
                      <span className="text-slate-500 block">Material</span>
                      <span className="text-slate-200 font-medium">{d.material}</span>
                    </div>
                    <div className="bg-slate-800/60 rounded px-2 py-1.5">
                      <span className="text-slate-500 block">Inventory</span>
                      <span className="text-slate-200 font-medium">{d.inventory_days_cover}d cover</span>
                    </div>
                    <div className="bg-slate-800/60 rounded px-2 py-1.5">
                      <span className="text-slate-500 block">Delays</span>
                      <span className="text-slate-200 font-medium">{d.supplier_delay_count} past</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between mt-3">
                    <span className={`text-xs flex items-center gap-1 ${d.hasPackage ? 'text-emerald-400' : 'text-slate-500'}`}>
                      {d.hasPackage ? (
                        <><CheckCircle2 className="w-3 h-3" /> Resolution Package Ready</>
                      ) : (
                        'Awaiting Analysis'
                      )}
                    </span>
                    <button
                      onClick={() => navigate(`/shipments/${d.shipment_id}`)}
                      className="flex items-center gap-1 text-xs text-slate-300 hover:text-white border border-slate-700 hover:border-slate-500 px-2 py-1 rounded transition-colors"
                    >
                      View Details <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ── Maritime Intelligence Strip ── */}
      <div className="px-8 pb-2">
        <MaritimeStrip />
      </div>

      {/* ── Full Maritime Intelligence Panel ── */}
      <div className="px-8 pb-4">
        <MaritimeIntelligencePanel />
      </div>

      {/* ── Supply Chain Health Bar ── */}
      <div className="px-8 pb-8">
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 px-6 py-4 flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="shrink-0">
            <div className="flex items-center gap-2">
              <Activity className={`w-4 h-4 ${healthText}`} />
              <span className="text-sm font-semibold text-white">Supply Chain Health Score</span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Based on {shipments.length} active shipments · {criticalCount} critical alert{criticalCount !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex-1 flex items-center gap-4 min-w-0">
            <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${healthBar}`}
                style={{ width: `${healthScore}%` }}
              />
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


function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  const colorMap: Record<string, string> = {
    critical: 'border-red-500/30 text-red-300',
    high: 'border-orange-500/30 text-orange-300',
    medium: 'border-yellow-500/30 text-yellow-300',
    low: 'border-slate-700 text-slate-200',
  };
  const cls = colorMap[color] || colorMap.low;
  return (
    <div className={`rounded-lg border bg-slate-800/60 px-3 py-2 ${cls}`}>
      <p className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</p>
      <p className="text-sm font-bold mt-0.5">{value}</p>
    </div>
  );
}


function MaritimeStrip() {
  const { data: portData } = useQuery({
    queryKey: ['port-congestion'],
    queryFn: () => maritimeApi.getAllPortCongestion().then((res) => res.data),
    refetchInterval: 120_000,
  });

  const { data: tariffData } = useQuery({
    queryKey: ['tariffs-us-china'],
    queryFn: () => maritimeApi.getRouteTariffs('CHN', 'USA', 'electronics').then((res) => res.data),
    refetchInterval: 300_000,
  });

  const congestedPorts = portData?.congested_ports || [];
  const tariffRate = tariffData?.average_rate || 0;
  const tariffSeverity = tariffData?.severity || 'low';

  const severityColor: Record<string, string> = {
    critical: 'text-red-400',
    high: 'text-orange-400',
    medium: 'text-yellow-400',
    low: 'text-green-400',
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 px-6 py-3 flex items-center gap-6 overflow-x-auto">
      <div className="flex items-center gap-2 shrink-0">
        <Anchor className="w-4 h-4 text-blue-400" />
        <span className="text-xs font-semibold text-white uppercase tracking-wide">Maritime Intel</span>
      </div>

      <div className="h-6 w-px bg-slate-700" />

      {/* Port Congestion */}
      <div className="flex items-center gap-2 shrink-0">
        <MapPin className="w-3.5 h-3.5 text-orange-400" />
        <span className="text-xs text-slate-400">Congested Ports:</span>
        <span className={`text-xs font-bold ${congestedPorts.length > 3 ? 'text-red-400' : congestedPorts.length > 0 ? 'text-yellow-400' : 'text-green-400'}`}>
          {congestedPorts.length}
        </span>
        {congestedPorts.slice(0, 3).map((p: any) => (
          <span key={p.port_name} className="text-xs text-slate-500 capitalize">
            {p.port_name} ({p.congestion_ratio}x)
          </span>
        ))}
      </div>

      <div className="h-6 w-px bg-slate-700" />

      {/* Tariff */}
      <div className="flex items-center gap-2 shrink-0">
        <DollarSign className="w-3.5 h-3.5 text-yellow-400" />
        <span className="text-xs text-slate-400">CN→US Tariff:</span>
        <span className={`text-xs font-bold ${severityColor[tariffSeverity]}`}>
          {tariffRate}%
        </span>
      </div>

      <div className="h-6 w-px bg-slate-700" />

      {/* Sanctions */}
      <div className="flex items-center gap-2 shrink-0">
        <Shield className="w-3.5 h-3.5 text-emerald-400" />
        <span className="text-xs text-slate-400">Sanctions:</span>
        <span className="text-xs font-bold text-green-400">OFAC + UN Active</span>
      </div>
    </div>
  );
}

function MaritimeIntelligencePanel() {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
      <MaritimeIntelligence />
    </div>
  );
}
