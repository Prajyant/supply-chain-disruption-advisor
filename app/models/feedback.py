"""Pydantic models for the reinforcement learning feedback loop."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ContextSnapshot(BaseModel):
    """Slim context snapshot — only the 5 fields that matter for forensics.

    Does NOT store full NodeContext to avoid bloating feedback.db.
    """

    node_id: str
    risk_score: float
    days_buffer: Optional[int] = None
    active_shipment_count: int = 0
    financial_exposure_usd: Optional[float] = None


class FeedbackRecord(BaseModel):
    """Single user feedback event stored in SQLite."""

    feedback_id: str
    execution_id: str
    playbook_id: str
    decision: str  # "accepted" | "rejected" | "partial"
    user_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    comment: Optional[str] = None
    context_snapshot: ContextSnapshot


class PlaybookStats(BaseModel):
    """Aggregated stats for a playbook — single source of truth."""

    playbook_id: str
    total_executions: int = 0
    accepted: int = 0
    rejected: int = 0
    partial: int = 0
    acceptance_rate: float = 0.0
    last_triggered: Optional[datetime] = None
    avg_response_time_hours: Optional[float] = None
