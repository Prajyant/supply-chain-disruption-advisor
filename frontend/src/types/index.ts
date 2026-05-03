export interface User {
  id: string;
  username: string;
  email?: string;
  role: 'admin' | 'manager' | 'viewer' | 'buyer';
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
}

export interface Edge {
  from: string;
  to: string;
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

export interface ShipmentInput {
  shipment_id: string;
  supplier: string;
  origin: string;
  destination: string;
  route_nodes: string[];
  imo_number?: string | null;
  vessel_name?: string | null;
  vessel_latitude?: number | null;
  vessel_longitude?: number | null;
  vessel_status?: string | null;
  vessel_speed_knots?: number | null;
  vessel_course_degrees?: number | null;
  vessel_progress_percent?: number | null;
  flight_callsign?: string | null;
  flight_icao24?: string | null;
  flight_altitude_m?: number | null;
  transport_mode: string;
  material: string;
  quantity: number;
  lead_time_days: number;
  inventory_days_cover: number;
  supplier_delay_count: number;
  priority_score?: number;
  priority?: string;
  declared_value_usd: number;
  departure_date?: string | null;
  eta_date?: string | null;
  target_delivery_date?: string | null;
  [key: string]: any;
}

export interface EventExplanation {
  feature_name: string;
  impact_score: number;
  evidence_summary: string;
  source_events: string[];
}

export interface EvidenceEvent {
  event_id?: string;
  source: string;
  severity: string;
  title: string;
  summary: string;
  url: string;
  detected_at?: string;
  metadata: Record<string, any>;
}

export interface ShipmentRiskAdviceResponse {
  shipment_id: string;
  risk_score: number;
  risk_level: string;
  decision: string;
  reason: string;
  confidence_score: number;
  scoring_method: string;
  reasoning_method: string;
  escalation_required: boolean;
  signals: string[];
  features: Record<string, number>;
  mitigation_plan: string[];
  recommended_actions: string[];
  evidence_events: EvidenceEvent[];
  context_events: EvidenceEvent[];
  event_explanations: EventExplanation[];
  // Financial impact fields
  financial_exposure_usd: number;
  daily_cost_usd: number;
  mitigation_cost_usd: number;
  net_saving_if_act_now_usd: number;
  production_lines_at_risk: string[];
  halt_date_estimate: string | null;
}

export interface StrandsShipmentRiskResponse {
  agent: string;
  strands_sdk_available: boolean;
  orchestration_method: string;
  steps: string[];
  result: ShipmentRiskAdviceResponse;
}

// ==================== Phase 3 Types ====================

export interface ContextSummary {
  shipment_count: number;
  order_count: number;
  risk_count: number;
  has_critical_risk: boolean;
}

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

export type ShipmentStatus = 'in_transit' | 'delivered' | 'rerouted' | 'cancelled' | 'delayed';

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
  pending_orders: any[];
  risk_history: any[];
  connected_news: any[];
  upstream_nodes: any[];
  downstream_nodes: any[];
  context_summary: ContextSummary;
}

export interface Playbook {
  id: string;
  name: string;
  description: string;
  trigger_conditions: Record<string, any>;
  trigger: {
    severity_gte?: string;
    min_severity?: string;
    disruption_type?: string;
    disruption_types?: string[];
    requires_active_shipment?: boolean;
    requires_low_buffer?: boolean;
    buffer_threshold?: number;
    [key: string]: any;
  };
  actions: any[];
  enabled: boolean;
  acceptance_rate: number;
  total_executions: number;
  times_triggered?: number;
  category?: string;
}

export interface PlaybookExecution {
  id: string;
  execution_id: string;
  playbook_id: string;
  playbook_name: string;
  node_id: string;
  node_name: string;
  severity: string;
  disruption_type: string;
  actions_taken: string[];
  actions: {
    description: string;
    target: string;
    urgency: string;
    [key: string]: any;
  }[];
  status: string;
  triggered_at: string;
  feedback?: string;
  is_simulation?: boolean;
}

export interface PlaybookWithStats extends Playbook {
  recent_executions?: PlaybookExecution[];
}
