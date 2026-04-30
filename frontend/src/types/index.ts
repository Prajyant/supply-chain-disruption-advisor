export interface User {
  id: string;
  username: string;
  role: 'admin' | 'manager' | 'viewer';
}

export interface RiskAssessment {
  risk_id: string;
  source: string;
  reference_id: string;
  detected_at: string;
  disruption_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  confidence: number;
  signals: string[];
  recommendations: string[];
  summary: string;
  headline: string;
  metadata: Record<string, any>;
}

export interface Node {
  id: string;
  type: 'supplier' | 'warehouse' | 'plant';
  name: string;
  location: string;
  risk_score: number;
  status: 'normal' | 'at_risk' | 'critical' | 'offline';
  criticality: 'low' | 'medium' | 'high';
  context_summary?: NodeContextSummary;
}

export interface Edge {
  from_node: string;
  to_node: string;
  type: 'supplies_to' | 'ships_to';
  material_type: string;
  volume: number;
  lead_time: number;
}

export interface Network {
  nodes: Node[];
  edges: Edge[];
  metadata: {
    last_updated: string;
    total_risks: number;
  };
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  recommendations?: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

// ==================== Phase 2: Intelligence Layer Types ====================

export type ShipmentStatus = 'in_transit' | 'delivered' | 'rerouted' | 'cancelled' | 'delayed';

export interface ShipmentSummary {
  shipment_id: string;
  supplier: string;
  material: string;
  status: ShipmentStatus;
  eta_days: number;
  origin: string;
  destination: string;
  tracking_number: string;
  departure_date: string;
  last_updated: string;
}

export interface OrderSummary {
  order_id: string;
  supplier: string;
  material: string;
  quantity: number;
  status: 'pending' | 'in_production' | 'shipped' | 'fulfilled';
  expected_date: string;
  stock_coverage_days?: number;
}

export interface RiskHistoryEntry {
  risk_id: string;
  severity: string;
  disruption_type: string;
  detected_at: string;
  summary: string;
  source: string;
}

export interface NewsArticleSummary {
  news_id: string;
  headline: string;
  region: string;
  date: string;
  relevance_score: number;
}

export interface NodeContextSummary {
  shipment_count: number;
  order_count: number;
  risk_count: number;
  has_critical_risk: boolean;
}

export interface NodeContext {
  id: string;
  type: string;
  name: string;
  location: string;
  risk_score: number;
  direct_risk: number;
  derived_risk: number;
  status: string;
  criticality: string;
  financial_exposure_usd: number | null;
  days_buffer: number | null;
  active_shipments: ShipmentSummary[];
  pending_orders: OrderSummary[];
  risk_history: RiskHistoryEntry[];
  connected_news: NewsArticleSummary[];
  upstream_nodes: Node[];
  downstream_nodes: Node[];
  context_summary: NodeContextSummary;
}
