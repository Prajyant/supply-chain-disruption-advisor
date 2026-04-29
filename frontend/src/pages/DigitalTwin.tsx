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

const nodeTypes = {};

export function DigitalTwin() {
  const { data: network, isLoading, refetch } = useQuery({
    queryKey: ['network'],
    queryFn: () => networkApi.getNetwork().then((res) => res.data),
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  React.useEffect(() => {
    if (network) {
      const flowNodes: Node[] = network.nodes.map((node: any) => ({
        id: node.id,
        type: 'default',
        position: { x: Math.random() * 400, y: Math.random() * 400 },
        data: {
          label: (
            <div className="text-center">
              <div className="font-semibold text-sm">{node.name}</div>
              <div className="text-xs text-slate-400">{node.type}</div>
              <div className="text-xs mt-1">
                Risk: {Math.round(node.risk_score * 100)}%
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
      }));

      const flowEdges: Edge[] = network.edges.map((edge: any) => ({
        id: `${edge.from_node}-${edge.to_node}`,
        source: edge.from_node,
        target: edge.to_node,
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

      <div className="flex-1 bg-slate-900 rounded-lg border border-slate-800 overflow-hidden">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
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
          <div className="w-3 h-3 rounded-full bg-danger-500" />
          <span className="text-slate-400">Critical</span>
        </div>
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
