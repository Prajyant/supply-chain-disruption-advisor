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

export interface ShipmentInput {
  shipment_id: string;
  supplier: string;
  origin: string;
  destination: string;
  route_nodes: string[];
  vessel_imo?: number | null;
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
}

export interface StrandsShipmentRiskResponse {
  agent: string;
  strands_sdk_available: boolean;
  orchestration_method: string;
  steps: string[];
  result: ShipmentRiskAdviceResponse;
}
