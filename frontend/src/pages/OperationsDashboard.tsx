import { useQuery } from '@tanstack/react-query';
import { loadDemoShipments } from '../services/shipmentData';
import { useShipmentStore } from '../store/shipmentStore';
import { networkApi, maritimeApi } from '../services/api';
import { MaritimeIntelligence } from '../components/MaritimeIntelligence';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import React from 'react';
import { AlertTriangle, CheckCircle2, ExternalLink, Activity, Anchor, MapPin, Shield, DollarSign } from 'lucide-react';
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

export function OperationsDashboard() {
  const navigate = useNavigate();

  const { data: demoShipments = [] } = useQuery({
    queryKey: ['demo-shipments'],
    queryFn: loadDemoShipments,
  });

  const { uploadedShipments } = useShipmentStore();
  const shipments = uploadedShipments || demoShipments;

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

  // ── Derive disruptions from shipments ──────────────────────────────
  const disruptions = shipments
    .map((s) => {
      const riskScore = 4 + Math.random() * 6;
      const level = riskScore >= 8 ? 'critical' : riskScore >= 6 ? 'high' : 'medium';
      const inventoryDays = s.inventory_days_cover ?? 14;
      const haltDate = new Date();
      haltDate.setDate(haltDate.getDate() + Math.max(1, Math.floor(inventoryDays * 0.7)));
      const hasPackage = level === 'critical' || level === 'high';
      return { ...s, riskScore, level, haltDate, hasPackage };
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
                  className={`rounded-lg border p-4 ${RISK_COLORS[d.level]}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded uppercase ${PILL[d.level]}`}>
                          {d.level}
                        </span>
                        <span className="text-xs font-mono text-slate-400">{d.shipment_id}</span>
                      </div>
                      <p className="text-sm font-semibold text-white mt-1 truncate">{d.supplier}</p>
                      <p className="text-xs text-slate-400">{d.origin} → {d.destination}</p>
                    </div>
                    <AlertTriangle className={`w-5 h-5 shrink-0 mt-0.5 ${d.level === 'critical' ? 'text-red-400' : 'text-orange-400'}`} />
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs mt-3">
                    <div className="bg-slate-800/60 rounded px-2 py-1.5">
                      <span className="text-slate-500 block">Affected material</span>
                      <span className="text-slate-200 font-medium">{d.material}</span>
                    </div>
                    <div className="bg-slate-800/60 rounded px-2 py-1.5">
                      <span className="text-slate-500 block">Est. halt date</span>
                      <span className="text-slate-200 font-medium">{d.haltDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
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
