import { useQuery } from '@tanstack/react-query';
import { networkApi } from '../services/api';
import { NodeContext, ShipmentStatus } from '../types';
import {
  X, Package, AlertTriangle, Newspaper, ShoppingCart,
  Truck, Clock, MapPin, ArrowUpRight, ArrowDownRight,
  Shield,
} from 'lucide-react';
import React, { Component, ErrorInfo, ReactNode } from 'react';

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

// ==================== Status Badges ====================

const statusConfig: Record<ShipmentStatus, { label: string; color: string; bg: string }> = {
  in_transit: { label: 'In Transit', color: 'text-blue-400', bg: 'bg-blue-500/15' },
  delivered: { label: 'Delivered', color: 'text-emerald-400', bg: 'bg-emerald-500/15' },
  rerouted: { label: 'Rerouted', color: 'text-amber-400', bg: 'bg-amber-500/15' },
  cancelled: { label: 'Cancelled', color: 'text-red-400', bg: 'bg-red-500/15' },
  delayed: { label: 'Delayed', color: 'text-orange-400', bg: 'bg-orange-500/15' },
};

function StatusBadge({ status }: { status: ShipmentStatus }) {
  const cfg = statusConfig[status] || statusConfig.in_transit;
  return (
    <span className={`status-badge ${cfg.color} ${cfg.bg}`}>
      {cfg.label}
    </span>
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

function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'text-red-400';
    case 'high': return 'text-orange-400';
    case 'medium': return 'text-amber-400';
    case 'low': return 'text-slate-400';
    default: return 'text-slate-400';
  }
}

// ==================== Tab Types ====================

type TabKey = 'shipments' | 'orders' | 'risks' | 'news';

const tabs: { key: TabKey; label: string; icon: typeof Package }[] = [
  { key: 'shipments', label: 'Shipments', icon: Truck },
  { key: 'orders', label: 'Orders', icon: ShoppingCart },
  { key: 'risks', label: 'Risk History', icon: AlertTriangle },
  { key: 'news', label: 'News', icon: Newspaper },
];

// ==================== Main Component ====================

interface NodeDetailProps {
  nodeId: string;
  onClose: () => void;
}

function NodeDetailInner({ nodeId, onClose }: NodeDetailProps) {
  const [activeTab, setActiveTab] = React.useState<TabKey>('shipments');

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
  const shipments = context.active_shipments || [];
  const orders = context.pending_orders || [];
  const riskHistory = context.risk_history || [];
  const news = context.connected_news || [];
  const upstreamNodes = context.upstream_nodes || [];
  const downstreamNodes = context.downstream_nodes || [];

  return (
    <div className={`node-detail-panel ${borderClass}`}>
      {/* Header */}
      <div className="p-6 border-b border-slate-800">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              context.type === 'supplier' ? 'bg-indigo-500/20' :
              context.type === 'warehouse' ? 'bg-cyan-500/20' : 'bg-emerald-500/20'
            }`}>
              <Package className={`w-5 h-5 ${
                context.type === 'supplier' ? 'text-indigo-400' :
                context.type === 'warehouse' ? 'text-cyan-400' : 'text-emerald-400'
              }`} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">{context.name}</h2>
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <span className="capitalize">{context.type}</span>
                <span>·</span>
                <MapPin className="w-3 h-3" />
                <span>{context.location}</span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Risk Score + Metrics */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-800/60 rounded-lg p-3 text-center">
            <div className={`text-2xl font-bold ${
              riskPercent >= 80 ? 'text-red-400' : riskPercent >= 50 ? 'text-amber-400' : 'text-emerald-400'
            }`}>
              {riskPercent}%
            </div>
            <div className="text-xs text-slate-500">Risk Score</div>
          </div>
          {context.days_buffer !== null && context.days_buffer !== undefined && (
            <div className="bg-slate-800/60 rounded-lg p-3 text-center">
              <div className={`text-2xl font-bold ${
                context.days_buffer <= 2 ? 'text-red-400' : context.days_buffer <= 5 ? 'text-amber-400' : 'text-emerald-400'
              }`}>
                {context.days_buffer}d
              </div>
              <div className="text-xs text-slate-500">Buffer</div>
            </div>
          )}
          <div className="bg-slate-800/60 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-slate-200">
              {summary.shipment_count}
            </div>
            <div className="text-xs text-slate-500">Shipments</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          let count = 0;
          if (tab.key === 'shipments') count = shipments.length;
          if (tab.key === 'orders') count = orders.length;
          if (tab.key === 'risks') count = riskHistory.length;
          if (tab.key === 'news') count = news.length;

          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-3 text-xs font-medium transition-colors ${
                isActive
                  ? 'text-indigo-400 border-b-2 border-indigo-400'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
              {count > 0 && (
                <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] ${
                  isActive ? 'bg-indigo-500/20 text-indigo-300' : 'bg-slate-800 text-slate-500'
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {activeTab === 'shipments' && (
          shipments.length > 0 ? (
            shipments.map((s) => (
              <div key={s.shipment_id} className="shipment-card">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-white">{s.material}</span>
                  <StatusBadge status={s.status as ShipmentStatus} />
                </div>
                <div className="space-y-1 text-xs text-slate-400">
                  {s.tracking_number && (
                    <div className="flex items-center gap-1.5">
                      <Package className="w-3 h-3" /> {s.tracking_number}
                    </div>
                  )}
                  <div className="flex items-center gap-1.5">
                    <MapPin className="w-3 h-3" /> {s.origin}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3 h-3" /> ETA: {s.eta_days} days
                  </div>
                </div>
                {s.status === 'in_transit' && s.eta_days > 0 && (
                  <div className="eta-progress mt-2">
                    <div
                      className="eta-progress-bar"
                      style={{ width: `${Math.min(100, Math.max(10, 100 - s.eta_days * 5))}%` }}
                    />
                  </div>
                )}
              </div>
            ))
          ) : (
            <EmptyState icon={Truck} message="No active shipments" />
          )
        )}

        {activeTab === 'orders' && (
          orders.length > 0 ? (
            orders.map((o) => (
              <div key={o.order_id} className="shipment-card">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-white">{o.material}</span>
                  <span className="text-xs text-slate-500">{o.order_id}</span>
                </div>
                <div className="text-xs text-slate-400 space-y-1">
                  <div>Supplier: {o.supplier}</div>
                  {o.quantity > 0 && <div>Qty: {o.quantity.toLocaleString()}</div>}
                </div>
              </div>
            ))
          ) : (
            <EmptyState icon={ShoppingCart} message="No pending orders" />
          )
        )}

        {activeTab === 'risks' && (
          riskHistory.length > 0 ? (
            <div className="risk-timeline">
              {riskHistory.map((r) => (
                <div key={r.risk_id} className="risk-timeline-item">
                  <div className={`risk-timeline-dot ${getSeverityColor(r.severity)}`} />
                  <div className="flex-1 ml-3">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-xs font-medium uppercase ${getSeverityColor(r.severity)}`}>
                        {r.severity}
                      </span>
                      <span className="text-xs text-slate-600">{r.disruption_type}</span>
                    </div>
                    <p className="text-sm text-slate-300">{r.summary}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={AlertTriangle} message="No risk history" />
          )
        )}

        {activeTab === 'news' && (
          news.length > 0 ? (
            news.map((n) => (
              <div key={n.news_id} className="shipment-card">
                <p className="text-sm text-white mb-1">{n.headline}</p>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  <span>{n.region}</span>
                  <span>Relevance: {Math.round(n.relevance_score * 100)}%</span>
                </div>
              </div>
            ))
          ) : (
            <EmptyState icon={Newspaper} message="No connected news" />
          )
        )}
      </div>

      {/* Impact Footer */}
      {(upstreamNodes.length > 0 || downstreamNodes.length > 0) && (
        <div className="p-4 border-t border-slate-800">
          <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">Impact Chain</h4>
          <div className="flex gap-4 text-xs">
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

function EmptyState({ icon: Icon, message }: { icon: typeof Package; message: string }) {
  return (
    <div className="text-center py-8">
      <Icon className="w-8 h-8 text-slate-700 mx-auto mb-2" />
      <p className="text-sm text-slate-500">{message}</p>
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
