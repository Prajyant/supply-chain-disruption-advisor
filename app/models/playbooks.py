"""Pydantic models for the automated playbook system."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


# ==================== SEVERITY ORDERING ====================
# 🔴 Critical Fix: Single constant — no inline string comparisons.
SEVERITY_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


# ==================== TRIGGER & ACTION ====================


class PlaybookTrigger(BaseModel):
    """Condition that fires a playbook."""

    disruption_type: str  # "logistics", "natural_disaster", "operations", etc.
    min_severity: str  # "low" | "medium" | "high" | "critical"
    requires_active_shipment: bool = False
    requires_low_buffer: bool = False  # days_buffer <= 3
    buffer_threshold: int = 3  # Customizable threshold for buffer check


class PlaybookAction(BaseModel):
    """Single action step in a playbook response."""

    action_type: str
    description: str
    urgency: str  # "immediate" | "within_24h" | "next_cycle"
    target: str  # "procurement" | "logistics" | "executive" | "supplier"


# ==================== PLAYBOOK DEFINITION ====================


class Playbook(BaseModel):
    """Pre-defined response template.

    Note: acceptance_rate is NOT stored here — it's always fetched
    from FeedbackService as the single source of truth.
    """

    id: str
    name: str
    description: str
    trigger: PlaybookTrigger
    actions: list[PlaybookAction]
    enabled: bool = True
    category: str = "general"  # For UI color-coding


# ==================== EXECUTION RECORD ====================


class PlaybookExecution(BaseModel):
    """Record of a playbook being triggered."""

    execution_id: str
    playbook_id: str
    playbook_name: str
    risk_id: str
    node_id: str
    node_name: str
    supplier: str = ""
    severity: str = ""
    disruption_type: str = ""
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actions: list[PlaybookAction]
    status: str = "pending"  # "pending" | "accepted" | "rejected" | "partial"
    user_feedback: Optional[str] = None
    is_simulation: bool = False


# ==================== API REQUEST/RESPONSE ====================


class PlaybookFeedbackRequest(BaseModel):
    """Request to submit feedback on a playbook execution."""

    decision: str  # "accepted" | "rejected" | "partial"
    comment: Optional[str] = None


class PlaybookWithStats(BaseModel):
    """Playbook definition enriched with stats from FeedbackService."""

    id: str
    name: str
    description: str
    trigger: PlaybookTrigger
    actions: list[PlaybookAction]
    enabled: bool
    category: str
    # Stats — always from FeedbackService, never cached
    times_triggered: int = 0
    acceptance_rate: Optional[float] = None
    last_triggered: Optional[datetime] = None


class SimulateRequest(BaseModel):
    """Request to simulate a playbook against a node."""

    node_id: Optional[str] = None  # If None, uses highest-risk node
