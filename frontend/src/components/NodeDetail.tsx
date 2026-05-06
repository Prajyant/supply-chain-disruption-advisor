import { useQuery } from '@tanstack/react-query';
import { networkApi } from '../services/api';
import { NodeContext } from '../types';
import {
  X, Package, AlertTriangle,
  MapPin, ArrowUpRight, ArrowDownRight,
  Shield, Truck,
} from 'lucide-react';
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { useViewMode } from '../context/ViewModeContext';

// ==================== Error Boundary ====================

interface ErrorBoundaryProps { children: ReactNode; onClose: () => void; }
interface ErrorBoundaryState { hasError: boolean; }

class NodeDetailErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('NodeDetail error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="node-detail-panel border-l-slate-600">
          <div className="flex items-center justify-between p-6 border-b border-slate-800">
            <h2 className="text-lg font-semibold text-white">Error</h2>
            <button onClick={this.props.onClose} className="text-slate-400 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="p-6 text-center">
            <AlertTriangle className="w-12 h-12 text-orange-400 mx-auto mb-3" />
            <p className="text-slate-300">Failed to load node details.</p>
            <p className="text-sm text-slate-500 mt-1">This node may not have context data available.</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ==================== Skeleton Loader ====================

function NodeDetailSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-pulse">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 bg-slate-800 rounded-lg" />
        <div className="flex-1">
          <div className="h-5 bg-slate-800 rounded w-3/4 mb-2" />
          <div className="h-3 bg-slate-800 rounded w-1/2" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 bg-slate-800 rounded-lg" />
        ))}
      </div>
      <div className="space-y-3">
        <div className="h-4 bg-slate-800 rounded w-1/3" />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 bg-slate-800 rounded-lg" />
        ))}
      </div>
    </div>
  );
}

// ==================== Risk Level Border Color ====================

function getBorderColor(status: string): string {
  switch (status) {
    case 'critical': return 'border-l-red-500';
    case 'at_risk': return 'border-l-amber-500';
    case 'normal': return 'border-l-emerald-500';
    case 'offline': return 'border-l-slate-600';
    default: return 'border-l-slate-600';
  }
}

// ==================== Main Component ====================

interface NodeDetailProps {
  nodeId: string;
  onClose: () => void;
}

function NodeDetailInner({ nodeId, onClose }: NodeDetailProps) {
  const { viewMode } = useViewMode();
  const { data: context, isLoading, error } = useQuery<NodeContext>({
    queryKey: ['nodeContext', nodeId],
    queryFn: () => networkApi.getNodeContext(nodeId).then((r) => r.data),
    enabled: !!nodeId,
  });

  if (isLoading) {
    return (
      <div className="node-detail-panel border-l-slate-700">
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <h2 className="text-lg font-semibold text-white">Loading...</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <NodeDetailSkeleton />
      </div>
    );
  }

  if (error || !context) {
    return (
      <div className="node-detail-panel border-l-slate-600">
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <h2 className="text-lg font-semibold text-white">Node Details</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 text-center">
          <Shield className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">No context data available for this node.</p>
        </div>
      </div>
    );
  }

  const borderClass = getBorderColor(context.status);
  const rawRisk = context.risk_score;
  const riskPercent = (typeof rawRisk === 'number' && !isNaN(rawRisk)) ? Math.round(rawRisk * 100) : 0;
  const summary = context.context_summary || { shipment_count: 0, order_count: 0, risk_count: 0, has_critical_risk: false };
  const upstreamNodes = context.upstream_nodes || [];
  const downstreamNodes = context.downstream_nodes || [];
  const shipments = context.active_shipments || [];

  return (
    <div className={`node-detail-panel ${borderClass}`}>
      {/* Header */}
      <div className="p-4 border-b border-slate-800">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              context.type === 'supplier' ? 'bg-indigo-500/20' :
              context.type === 'warehouse' ? 'bg-cyan-500/20' : 'bg-emerald-500/20'
            }`}>
              <Package className={`w-4 h-4 ${
                context.type === 'supplier' ? 'text-indigo-400' :
                context.type === 'warehouse' ? 'text-cyan-400' : 'text-emerald-400'
              }`} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">{context.name}</h2>
              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                <span className="capitalize">{context.type}</span>
                <span>·</span>
                <MapPin className="w-2.5 h-2.5" />
                <span>{context.location}</span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Risk Score + Metrics */}
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-slate-800/60 rounded-lg p-2 text-center">
            <div className={`text-lg font-bold ${
              riskPercent >= 80 ? 'text-red-400' : riskPercent >= 50 ? 'text-amber-400' : 'text-emerald-400'
            }`}>
              {riskPercent}%
            </div>
            <div className="text-[10px] text-slate-500">Risk Score</div>
          </div>
          <div className="bg-slate-800/60 rounded-lg p-2 text-center">
            <div className="text-lg font-bold text-slate-200">
              {summary.shipment_count}
            </div>
            <div className="text-[10px] text-slate-500">Shipments</div>
          </div>
        </div>

        {context.days_buffer !== null && context.days_buffer !== undefined && (
          <div className="mt-2 bg-slate-800/60 rounded-lg p-2 text-center">
            <div className={`text-base font-bold ${
              context.days_buffer <= 2 ? 'text-red-400' : context.days_buffer <= 5 ? 'text-amber-400' : 'text-emerald-400'
            }`}>
              {context.days_buffer} days
            </div>
            <div className="text-[10px] text-slate-500">Buffer Remaining</div>
          </div>
        )}
      </div>

      {/* Associated Shipments (Operations view) */}
      {viewMode === 'operations' && shipments.length > 0 && (
        <div className="p-3 border-b border-slate-800">
          <h4 className="text-[10px] font-medium text-slate-500 uppercase mb-2 flex items-center gap-1.5">
            <Truck className="w-3 h-3" />
            Associated Shipments
          </h4>
          <div className="space-y-1.5">
            {shipments.map((s) => (
              <div key={s.shipment_id} className="flex items-center justify-between rounded-md bg-slate-800/50 px-2.5 py-1.5">
                <div className="min-w-0">
                  <div className="text-xs font-medium text-white truncate">{s.shipment_id}</div>
                  <div className="text-[10px] text-slate-400 truncate">{s.origin} → {s.destination}</div>
                </div>
                <span className={`shrink-0 ml-2 rounded-full px-1.5 py-0.5 text-[9px] font-medium uppercase ${
                  s.status === 'delayed' ? 'bg-orange-500/15 text-orange-300' :
                  s.status === 'in_transit' ? 'bg-blue-500/15 text-blue-300' :
                  s.status === 'rerouted' ? 'bg-amber-500/15 text-amber-300' :
                  'bg-slate-700 text-slate-300'
                }`}>
                  {s.status.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Impact Chain */}
      {(upstreamNodes.length > 0 || downstreamNodes.length > 0) && (
        <div className="p-3 border-t border-slate-800">
          <h4 className="text-[10px] font-medium text-slate-500 uppercase mb-1.5">Impact Chain</h4>
          <div className="flex gap-3 text-xs">
            {upstreamNodes.length > 0 && (
              <div className="flex items-center gap-1 text-slate-400">
                <ArrowDownRight className="w-3 h-3 text-cyan-400" />
                <span>{upstreamNodes.length} upstream</span>
              </div>
            )}
            {downstreamNodes.length > 0 && (
              <div className="flex items-center gap-1 text-slate-400">
                <ArrowUpRight className="w-3 h-3 text-orange-400" />
                <span>{downstreamNodes.length} downstream</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Export with Error Boundary ====================

export function NodeDetail({ nodeId, onClose }: NodeDetailProps) {
  return (
    <NodeDetailErrorBoundary onClose={onClose}>
      <NodeDetailInner nodeId={nodeId} onClose={onClose} />
    </NodeDetailErrorBoundary>
  );
}
