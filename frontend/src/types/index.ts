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
