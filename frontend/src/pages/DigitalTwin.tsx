import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { networkApi } from '../services/api';
import ReactFlow, {
  Node, Background, Controls, MiniMap,
  useNodesState, useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import React from 'react';
import { RefreshCw, AlertTriangle, Network, ZoomIn, Info } from 'lucide-react';
import { NodeDetail } from '../components/NodeDetail';
import { useViewMode } from '../context/ViewModeContext';

function accentColor(status: string): string {
  switch (status) {
    case 'critical': return '#ef4444';
    case 'at_risk':  return '#f59e0b';
    case 'normal':   return '#22c55e';
    default:         return '#334155';
  }
}
function riskTextColor(score: number): string {
  if (score >= 0.8) return '#fca5a5';
  if (score >= 0.6) return '#fcd34d';
  if (score >= 0.3) return '#86efac';
  return '#94a3b8';
}

export function DigitalTwin() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const { viewMode } = useViewMode();
  const isOps = viewMode === 'operations';

  const { data: network, isLoading, refetch } = useQuery({
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
    const COL_X = { supplier: 0, warehouse: 380, plant: 760 };
    const ROW = 100;
    const maxCol = Math.max(suppliers.length, warehouses.length, plants.length);

    function layoutCol(items: any[], colX: number): Node[] {
      const startY = Math.max(0, (maxCol * ROW - items.length * ROW) / 2);
      return items.map((n: any, i: number) => {
        const risk   = n.risk_score ?? 0;
        const accent = accentColor(n.status);
        const typeEmoji = n.type === 'supplier' ? '🚢' : n.type === 'warehouse' ? '🔄' : '🏭';

        return {
          id: n.id,
          type: 'default',
          position: { x: colX, y: startY + i * ROW },
          data: {
            label: isOps ? (
              <div className="text-center">
                <div className="flex items-center justify-center gap-1 mb-0.5">
                  <span className="text-[11px]">{typeEmoji}</span>
                  <span className="font-semibold text-[11px] text-white leading-tight">{n.name}</span>
                </div>
                <div className="text-[9px]" style={{
                  color: n.status === 'critical' ? '#fca5a5' : n.status === 'at_risk' ? '#fcd34d' : '#86efac',
                }}>
                  {n.status === 'critical' ? '⛔ Critical' : n.status === 'at_risk' ? '⚠️ At Risk' : '✅ Normal'}
                </div>
                {n.location && <div className="text-[9px] text-slate-500 mt-0.5">{n.location}</div>}
              </div>
            ) : (
              <div className="text-center">
                <div className="flex items-center justify-center gap-1 mb-0.5">
                  <span className="text-[11px]">{typeEmoji}</span>
                  <span className="font-semibold text-[11px] text-white leading-tight">{n.name}</span>
                </div>
                {risk > 0 ? (
                  <div className="text-[10px] font-mono" style={{ color: riskTextColor(risk) }}>
                    Risk: {Math.round(risk * 100)}%
                  </div>
                ) : (
                  <div className="text-[9px] text-slate-600">No risk data</div>
                )}
              </div>
            ),
          },
          style: {
            background: '#0f172a',
            border: `2px solid ${accent}`,
            borderRadius: 10,
            padding: '10px 8px',
            width: 170,
            boxShadow: risk >= 0.6 ? `0 0 14px ${accent}35` : 'none',
          },
        };
      });
    }

    setNodes([
      ...layoutCol(suppliers, COL_X.supplier),
      ...layoutCol(warehouses, COL_X.warehouse),
      ...layoutCol(plants, COL_X.plant),
    ]);
    setEdges(network.edges.map((e: any, i: number) => ({
      id: `${e.from}-${e.to}-${i}`,
      source: e.from,
      target: e.to,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#334155', strokeWidth: 1.5, opacity: 0.6 },
      label: e.material_type,
      labelStyle: { fontSize: 8, fill: '#64748b' },
      labelBgStyle: { fill: '#020617', fillOpacity: 0.9 },
    })));
  }, [network, setNodes, setEdges, isOps]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  const totalNodes = network?.nodes?.length ?? 0;
  const atRiskCount = network?.nodes?.filter((n: any) =>
    n.status === 'at_risk' || n.status === 'critical'
  ).length ?? 0;

  if (isLoading) {
    return (
      <div className="p-8 space-y-4">
        <div className="skeleton h-8 w-48 rounded-lg" />
        <div className="skeleton h-[calc(100vh-160px)] rounded-xl" />
      </div>
    );
  }

  return (
    <div className="p-8 h-full flex flex-col gap-4">

      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Network className="w-6 h-6 text-primary-400" />
            {isOps ? 'Network Status' : 'Digital Twin'}
          </h1>
          <p className="page-subtitle">
            {isOps ? 'Live supply chain health' : 'Live supply chain network'} · {totalNodes} nodes
            {atRiskCount > 0 && (
              <span className="text-orange-400 ml-2">· {atRiskCount} at risk</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => refetch()} className="btn-secondary flex items-center gap-2 text-sm">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      {/* Alert strip */}
      {atRiskCount > 0 && (
        <div className="alert-warning shrink-0 py-2.5">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span className="text-sm">
            {atRiskCount} node{atRiskCount > 1 ? 's' : ''} showing elevated risk — click a node for details
          </span>
        </div>
      )}

      {/* Graph + detail panel */}
      <div className="flex-1 flex gap-4 overflow-hidden min-h-0">
        <div className={`bg-slate-950 rounded-xl border border-slate-800 overflow-hidden transition-all duration-200 ${
          selectedNodeId ? 'flex-1' : 'w-full'
        }`}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView fitViewOptions={{ padding: 0.15 }}
            minZoom={0.2} maxZoom={2.5}
          >
            <Background color="#1e293b" gap={24} />
            <Controls />
            <MiniMap
              nodeColor={(n) => accentColor(n.data?.status || 'normal')}
              maskColor="rgba(2,6,23,0.85)"
              style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }}
            />
          </ReactFlow>
        </div>

        {selectedNodeId && (
          <div className="w-72 shrink-0">
            <NodeDetail nodeId={selectedNodeId} onClose={() => setSelectedNodeId(null)} />
          </div>
        )}
      </div>

      {/* Footer legend */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-5">
          <Legend color="#22c55e" label="Normal" />
          <Legend color="#f59e0b" label="At Risk" />
          <Legend color="#ef4444" label="Critical" />
          <Legend color="#334155" label="Unknown" />
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <ZoomIn className="w-3.5 h-3.5" />
          <span>Scroll to zoom · Click node for details</span>
          <span className="mx-2 text-slate-800">·</span>
          <Info className="w-3.5 h-3.5" />
          <span>Auto-refreshes every 60s</span>
        </div>
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
      <span className="text-xs text-slate-500">{label}</span>
    </div>
  );
}
