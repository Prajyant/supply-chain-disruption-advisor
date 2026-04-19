from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    supplier_emails_path: str = "data/supplier_emails.csv"
    news_feed_path: str = "data/news_feed.csv"
    inventory_path: str = "data/inventory.csv"


class IngestResponse(BaseModel):
    ingested_events: int
    indexed_chunks: int
    message: str


class RetrievedContext(BaseModel):
    source: str
    reference_id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskAssessment(BaseModel):
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


class ChatRequest(BaseModel):
    question: str
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    supporting_context: list[RetrievedContext]
    recommendations: list[str]
