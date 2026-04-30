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
import { RefreshCw, Zap, Package, Truck, AlertTriangle } from 'lucide-react';
import React from 'react';
import { NodeDetail } from '../components/NodeDetail';

const nodeTypes = {};

export function DigitalTwin() {
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null);

  const { data: network, isLoading, refetch } = useQuery({
    queryKey: ['network'],
    queryFn: () => networkApi.getNetwork().then((res) => res.data),
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  React.useEffect(() => {
    if (network) {
      // Layered layout: suppliers left, warehouses center, plants right
      const typePositions: Record<string, { baseX: number; baseY: number }> = {
        supplier: { baseX: 50, baseY: 50 },
        warehouse: { baseX: 350, baseY: 120 },
        plant: { baseX: 650, baseY: 80 },
      };
      const typeCounters: Record<string, number> = {};

      const flowNodes: Node[] = network.nodes.map((node: any) => {
        const pos = typePositions[node.type] || { baseX: 200, baseY: 200 };
        const idx = typeCounters[node.type] || 0;
        typeCounters[node.type] = idx + 1;

        const ctx = node.context_summary || {};

        return {
          id: node.id,
          type: 'default',
          position: { x: pos.baseX + (idx % 2) * 180, y: pos.baseY + idx * 120 },
          data: {
            label: (
              <div className="text-center cursor-pointer">
                <div className="font-semibold text-sm">{node.name}</div>
                <div className="text-xs text-slate-400">{node.type}</div>
                <div className="text-xs mt-1">
                  Risk: {Math.round(node.risk_score * 100)}%
                </div>
                {/* Context badges */}
                <div className="flex items-center justify-center gap-2 mt-1.5">
                  {ctx.shipment_count > 0 && (
                    <span className="flex items-center gap-0.5 text-[10px] text-blue-400">
                      <Truck style={{ width: 10, height: 10 }} /> {ctx.shipment_count}
                    </span>
                  )}
                  {ctx.risk_count > 0 && (
                    <span className="flex items-center gap-0.5 text-[10px] text-orange-400">
                      <AlertTriangle style={{ width: 10, height: 10 }} /> {ctx.risk_count}
                    </span>
                  )}
                  {ctx.has_critical_risk && (
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  )}
                </div>
              </div>
            ),
            ...node,
          },
          style: {
            background: getNodeColor(node.status),
            border: `2px solid ${getBorderColor(node.status)}`,
            borderRadius: '8px',
            padding: '8px',
            width: 150,
          },
        };
      });

      const flowEdges: Edge[] = network.edges.map((edge: any) => ({
        id: `${edge.from}-${edge.to}`,
        source: edge.from,
        target: edge.to,
        type: 'smoothstep',
        animated: edge.type === 'supplies_to',
        style: { stroke: '#6366f1', strokeWidth: 2 },
        label: edge.material_type,
      }));

      setNodes(flowNodes);
      setEdges(flowEdges);
    }
  }, [network, setNodes, setEdges]);

  const handlePropagate = async () => {
    await networkApi.propagateRisk();
    refetch();
  };

  const handleNodeClick = (_event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse h-96 bg-slate-800 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="p-8 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Digital Twin</h1>
          <p className="text-slate-400">Supply chain network visualization</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handlePropagate}
            className="btn-primary flex items-center gap-2"
          >
            <Zap className="w-4 h-4" />
            Propagate Risk
          </button>
          <button
            onClick={() => refetch()}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-0 relative">
        {/* Graph */}
        <div className={`flex-1 bg-slate-900 rounded-lg border border-slate-800 overflow-hidden transition-all ${
          selectedNodeId ? 'mr-[380px]' : ''
        }`}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            fitView
            nodeTypes={nodeTypes}
          >
            <Background color="#1e293b" gap={16} />
            <Controls />
            <MiniMap
              nodeColor={(node) => getNodeColor(node.data?.status || 'normal')}
              maskColor="rgba(0, 0, 0, 0.8)"
            />
          </ReactFlow>
        </div>

        {/* Node Detail Panel — slides in from right */}
        {selectedNodeId && (
          <div className="absolute right-0 top-0 bottom-0 w-[380px] z-10">
            <NodeDetail
              nodeId={selectedNodeId}
              onClose={() => setSelectedNodeId(null)}
            />
          </div>
        )}
      </div>

      <div className="mt-4 flex gap-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-slate-400">Normal</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-yellow-500" />
          <span className="text-slate-400">At Risk</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-600" />
          <span className="text-slate-400">Critical</span>
        </div>
        <div className="ml-auto text-xs text-slate-600">Click a node to view details</div>
      </div>
    </div>
  );
}

function getNodeColor(status: string): string {
  const colors = {
    normal: '#10b981',
    at_risk: '#f59e0b',
    critical: '#dc2626',
    offline: '#64748b',
  };
  return colors[status as keyof typeof colors] || '#64748b';
}

function getBorderColor(status: string): string {
  const colors = {
    normal: '#059669',
    at_risk: '#d97706',
    critical: '#b91c1c',
    offline: '#475569',
  };
  return colors[status as keyof typeof colors] || '#475569';
}
