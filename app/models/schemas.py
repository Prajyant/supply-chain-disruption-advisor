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
