"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ==================== INGESTION SCHEMAS ====================


class IngestRequest(BaseModel):
    """Request for data ingestion."""
    supplier_emails_path: str = "data/supplier_emails.csv"
    news_feed_path: str = "data/news_feed.csv"
    inventory_path: str = "data/inventory.csv"
    use_realtime_news: bool = True
    use_live_emails: bool = False  # If True, reads from live Gmail inbox instead of CSV


class IngestResponse(BaseModel):
    """Response for data ingestion."""
    ingested_events: int
    indexed_chunks: int
    message: str


# ==================== RETRIEVAL SCHEMAS ====================


class RetrievedContext(BaseModel):
    """Retrieved context from vector search."""
    source: str
    reference_id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


# ==================== RISK SCHEMAS ====================


class RiskAssessment(BaseModel):
    """Risk assessment for a disruption event."""
    risk_id: str
    source: str
    reference_id: str
    detected_at: datetime
    disruption_type: str
    severity: str
    confidence: float
    signals: list[str]
    recommendations: list[str]
    summary: str
    headline: str = ""  # News headline for display
    metadata: dict[str, Any] = Field(default_factory=dict)


# ==================== CHAT SCHEMAS ====================


class ChatRequest(BaseModel):
    """Request for AI chat query."""
    question: str
    top_k: int = 5


class ChatResponse(BaseModel):
    """Response from AI chat query."""
    answer: str
    supporting_context: list[RetrievedContext]
    recommendations: list[str]


# ==================== AUTHENTICATION SCHEMAS ====================


class LoginRequest(BaseModel):
    """Request for user login."""
    username: str
    password: str


class User(BaseModel):
    """User information."""
    id: str
    username: str
    role: str


class LoginResponse(BaseModel):
    """Response for successful login."""
    access_token: str
    refresh_token: str
    user: User


# ==================== GRAPH/NETWORK SCHEMAS ====================


class Node(BaseModel):
    """A node in the supply chain graph."""
    id: str
    type: str  # "supplier", "warehouse", "plant"
    name: str
    location: str
    risk_score: float
    status: str  # "normal", "at_risk", "critical", "offline"
    criticality: str  # "low", "medium", "high"


class Edge(BaseModel):
    """An edge in the supply chain graph."""
    from_node: str
    to_node: str
    type: str  # "supplies_to", "ships_to"
    material_type: str
    volume: float
    lead_time: int


class NetworkResponse(BaseModel):
    """Response for network graph data."""
    nodes: list[Node]
    edges: list[Edge]
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeDetail(BaseModel):
    """Detailed information about a node."""
    id: str
    type: str
    name: str
    location: str
    risk_score: float
    direct_risk: float
    derived_risk: float
    status: str
    criticality: str


class NodeImpact(BaseModel):
    """Impact analysis for a node."""
    node_id: str
    upstream: list[Node]
    downstream: list[Node]


class PropagationResponse(BaseModel):
    """Response for risk propagation."""
    propagated: bool
    updated_nodes: list[str]
    total_risks: int


# ==================== WEBSOCKET SCHEMAS ====================


class RiskUpdateEvent(BaseModel):
    """Event for risk update notification."""
    type: str = "risk_updated"
    data: dict[str, Any]


class NodeStatusEvent(BaseModel):
    """Event for node status change notification."""
    type: str = "node_status_changed"
    data: dict[str, Any]


class AlertEvent(BaseModel):
    """Event for new alert notification."""
    type: str = "new_alert"
    data: dict[str, Any]


class IngestionCompleteEvent(BaseModel):
    """Event for ingestion completion notification."""
    type: str = "ingestion_complete"
    data: dict[str, Any]


# ==================== SHIPMENT SCHEMAS ====================


class ShipmentInput(BaseModel):
    """Input data for shipment risk analysis."""
    shipment_id: str
    supplier: str
    origin: str
    destination: str
    route_nodes: list[str] = Field(default_factory=list)
    imo_number: Optional[str] = None
    mmsi: Optional[str] = None
    vessel_name: Optional[str] = None
    vessel_latitude: Optional[float] = None
    vessel_longitude: Optional[float] = None
    vessel_status: Optional[str] = None
    vessel_speed_knots: Optional[float] = None
    vessel_course_degrees: Optional[float] = None
    vessel_progress_percent: Optional[float] = None
    flight_callsign: Optional[str] = None
    flight_icao24: Optional[str] = None
    flight_altitude_m: Optional[float] = None
    transport_mode: str = "sea"
    material: str
    quantity: float
    lead_time_days: float
    inventory_days_cover: float
    supplier_delay_count: int = 0
    priority: str | int = "normal"
    declared_value_usd: float = 0.0
    departure_date: Optional[str] = None
    eta_date: Optional[str] = None
    target_delivery_date: Optional[str] = None


class ShipmentRiskRequest(BaseModel):
    """Request for shipment risk scoring."""
    shipment: ShipmentInput
    intelligence_events: list[dict[str, Any]] = Field(default_factory=list)
    use_live_intelligence: bool = True


class ShipmentRiskResponse(BaseModel):
    """Response for shipment risk scoring."""
    shipment_id: str
    risk_score: float
    risk_level: str
    scoring_method: str
    model_version: str
    features: dict[str, float]
    signals: list[str]
    evidence_events: list[dict[str, Any]]
    context_events: list[dict[str, Any]]


class ShipmentRiskAdviceRequest(BaseModel):
    """Request for shipment risk advice."""
    shipment: ShipmentInput
    intelligence_events: list[dict[str, Any]] = Field(default_factory=list)
    use_live_intelligence: bool = True
    question: Optional[str] = None


class ShipmentRiskAdviceResponse(BaseModel):
    """Response for shipment risk advice."""
    shipment_id: str
    risk_score: float
    risk_level: str
    decision: str
    reason: str
    recommended_actions: list[str]
    confidence_score: int
    escalation_required: bool
    scoring_method: str
    reasoning_method: str
    model_version: str
    signals: list[str]
    features: dict[str, float]
    evidence_events: list[dict[str, Any]]
    context_events: list[dict[str, Any]]
    event_explanations: list[dict[str, Any]]
    # Financial impact fields
    financial_exposure_usd: float = 0.0
    daily_cost_usd: float = 0.0
    mitigation_cost_usd: float = 0.0
    net_saving_if_act_now_usd: float = 0.0
    production_lines_at_risk: list[str] = Field(default_factory=list)
    halt_date_estimate: Optional[str] = None


class StrandsShipmentRiskRequest(BaseModel):
    """Request for Strands-orchestrated shipment risk analysis."""
    shipment: ShipmentInput
    intelligence_events: list[dict[str, Any]] = Field(default_factory=list)
    use_live_intelligence: bool = True
    prefer_strands_sdk: bool = True
    question: Optional[str] = None


class StrandsShipmentRiskResponse(BaseModel):
    """Response for Strands-orchestrated shipment risk analysis."""
    agent: str
    strands_sdk_available: bool
    orchestration_method: str
    steps: list[str]
    result: ShipmentRiskAdviceResponse


# ==================== PHASE 3: NODE CONTEXT SCHEMAS ====================


class ShipmentSummary(BaseModel):
    """Compact shipment card for node context."""
    shipment_id: str
    supplier: str
    material: str
    status: str  # "in_transit", "delivered", "rerouted", "cancelled", "delayed"
    eta_days: int
    origin: str
    destination: str = ""
    tracking_number: str = ""
    departure_date: str = ""
    last_updated: str = ""


class OrderSummary(BaseModel):
    """Pending order card for node context."""
    order_id: str
    supplier: str
    material: str
    quantity: float
    status: str  # "pending", "in_production", "shipped", "fulfilled"
    expected_date: str = ""
    stock_coverage_days: Optional[int] = None


class RiskHistoryEntry(BaseModel):
    """Past risk event for node context timeline."""
    risk_id: str
    severity: str
    disruption_type: str
    detected_at: datetime
    summary: str
    source: str = ""


class NewsArticleSummary(BaseModel):
    """Linked news article for node context."""
    news_id: str
    headline: str
    region: str
    date: str
    relevance_score: float = 0.0


class NodeContextSummary(BaseModel):
    """Lightweight context summary cached per node for the graph view."""
    shipment_count: int = 0
    order_count: int = 0
    risk_count: int = 0
    has_critical_risk: bool = False


class NodeContext(BaseModel):
    """Complete knowledge card for a Digital Twin node."""
    id: str
    type: str
    name: str
    location: str
    risk_score: float
    direct_risk: float
    derived_risk: float
    status: str
    criticality: str
    financial_exposure_usd: Optional[float] = None
    days_buffer: Optional[int] = None
    active_shipments: list[ShipmentSummary] = Field(default_factory=list)
    pending_orders: list[OrderSummary] = Field(default_factory=list)
    risk_history: list[RiskHistoryEntry] = Field(default_factory=list)
    connected_news: list[NewsArticleSummary] = Field(default_factory=list)
    upstream_nodes: list[Node] = Field(default_factory=list)
    downstream_nodes: list[Node] = Field(default_factory=list)
    context_summary: NodeContextSummary = Field(default_factory=NodeContextSummary)


class ShipmentUpdateResult(BaseModel):
    """Result of processing a shipment status update."""
    shipment_id: str
    supplier: str
    old_status: str
    new_status: str
    node_id: Optional[str] = None
    risk_score_change: Optional[float] = None
