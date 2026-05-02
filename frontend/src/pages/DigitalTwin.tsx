import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { networkApi } from '../services/api';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { RefreshCw, Zap } from 'lucide-react';
import React from 'react';
import { NodeDetail } from '../components/NodeDetail';

export function DigitalTwin() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const { data: network, isLoading, refetch } = useQuery({
    queryKey: ['network'],
    queryFn: () => networkApi.getNetwork().then((res) => res.data),
    refetchInterval: 60_000,
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  React.useEffect(() => {
    if (!network) return;

    const suppliers = network.nodes.filter((n: any) => n.type === 'supplier');
    const warehouses = network.nodes.filter((n: any) => n.type === 'warehouse');
    const plants = network.nodes.filter((n: any) => n.type === 'plant');

    const COL_X = { supplier: 0, warehouse: 380, plant: 760 };
    const ROW_SPACING = 100;
    const maxCol = Math.max(suppliers.length, warehouses.length, plants.length);

    function layoutColumn(items: any[], colX: number): Node[] {
      const totalHeight = items.length * ROW_SPACING;
      const startY = Math.max(0, (maxCol * ROW_SPACING - totalHeight) / 2);

      return items.map((node: any, idx: number) => {
        const risk = node.risk_score ?? 0;
        const accent = accentColor(node.status);

        return {
          id: node.id,
          type: 'default',
          position: { x: colX, y: startY + idx * ROW_SPACING },
          data: { label: nodeLabel(node), ...node },
          style: {
            background: '#0f172a',
            border: `2px solid ${accent}`,
            borderRadius: '10px',
            padding: '10px 8px',
            width: 170,
            boxShadow: risk >= 0.6 ? `0 0 12px ${accent}40` : 'none',
          },
        };
      });
    }

    const flowNodes: Node[] = [
      ...layoutColumn(suppliers, COL_X.supplier),
      ...layoutColumn(warehouses, COL_X.warehouse),
      ...layoutColumn(plants, COL_X.plant),
    ];

    const flowEdges: Edge[] = network.edges.map((edge: any, idx: number) => ({
      id: `${edge.from}-${edge.to}-${idx}`,
      source: edge.from,
      target: edge.to,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#334155', strokeWidth: 1.5, opacity: 0.6 },
      label: edge.material_type,
      labelStyle: { fontSize: 8, fill: '#64748b' },
      labelBgStyle: { fill: '#020617', fillOpacity: 0.9 },
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [network, setNodes, setEdges]);

  const handlePropagate = async () => {
    await networkApi.scoreNodes();
    refetch();
  };

  const onNodeClick = useCallback((_event: any, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse h-96 bg-slate-800 rounded-lg" />
      </div>
    );
  }

  const totalNodes = network?.nodes?.length ?? 0;
  const atRiskCount = network?.nodes?.filter((n: any) => n.status === 'at_risk' || n.status === 'critical').length ?? 0;

  return (
    <div className="p-8 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Digital Twin</h1>
          <p className="text-slate-400">
            Live supply chain network · {totalNodes} nodes
            {atRiskCount > 0 && (
              <span className="text-orange-400 ml-2">· {atRiskCount} at risk</span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handlePropagate} className="btn-primary flex items-center gap-2">
            <Zap className="w-4 h-4" /> Score & Propagate
          </button>
          <button onClick={() => refetch()} className="btn-secondary flex items-center gap-2">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-4 overflow-hidden">
        <div className={`flex-1 bg-slate-950 rounded-lg border border-slate-800 overflow-hidden transition-all ${selectedNodeId ? 'w-2/3' : 'w-full'}`}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            minZoom={0.2}
            maxZoom={2.5}
          >
            <Background color="#1e293b" gap={24} />
            <Controls />
            <MiniMap
              nodeColor={(node) => accentColor(node.data?.status || 'normal')}
              maskColor="rgba(0, 0, 0, 0.85)"
              style={{ background: '#020617' }}
            />
          </ReactFlow>
        </div>

        {selectedNodeId && (
          <div className="w-1/3 min-w-[320px]">
            <NodeDetail nodeId={selectedNodeId} onClose={() => setSelectedNodeId(null)} />
          </div>
        )}
      </div>

      <div className="mt-3 flex justify-between items-center text-xs">
        <div className="flex gap-5">
          <Legend color="#22c55e" label="Normal" />
          <Legend color="#f59e0b" label="At Risk" />
          <Legend color="#ef4444" label="Critical" />
        </div>
        <span className="text-slate-600">Auto-refreshes every 60s · Click a node for details</span>
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
      <span className="text-slate-400">{label}</span>
    </div>
  );
}

function nodeLabel(node: any) {
  const risk = node.risk_score ?? 0;
  const riskPct = Math.round(risk * 100);
  const typeLabel = node.type === 'supplier' ? '🚢' : node.type === 'warehouse' ? '🔄' : '🏭';

  return (
    <div className="text-center">
      <div className="flex items-center justify-center gap-1 mb-1">
        <span className="text-xs">{typeLabel}</span>
        <span className="font-semibold text-xs text-white leading-tight">{node.name}</span>
      </div>
      {riskPct > 0 ? (
        <div className="text-xs font-mono" style={{ color: riskTextColor(risk) }}>
          Risk: {riskPct}%
        </div>
      ) : (
        <div className="text-[10px] text-slate-500">No risk data</div>
      )}
    </div>
  );
}

function accentColor(status: string): string {
  switch (status) {
    case 'critical': return '#ef4444';
    case 'at_risk': return '#f59e0b';
    case 'normal': return '#22c55e';
    default: return '#334155';
  }
}

function riskTextColor(score: number): string {
  if (score >= 0.8) return '#fca5a5';
  if (score >= 0.6) return '#fcd34d';
  if (score >= 0.3) return '#86efac';
  return '#94a3b8';
}
