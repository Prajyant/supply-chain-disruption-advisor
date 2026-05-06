"""Automated Playbook Engine — rule-based response system.

Evaluates risk events against pre-defined playbook triggers and generates
actionable response plans. Uses asyncio.Lock() for thread safety (🔴 Critical Fix #1).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.models.playbooks import (
    SEVERITY_ORDER,
    Playbook,
    PlaybookAction,
    PlaybookExecution,
    PlaybookTrigger,
    PlaybookWithStats,
)
from app.models.schemas import NodeContext, RiskAssessment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 8 Built-in Playbooks
# ---------------------------------------------------------------------------

BUILT_IN_PLAYBOOKS: list[Playbook] = [
    # 1. Port Congestion Reroute
    Playbook(
        id="pb_port_congestion_reroute",
        name="Port Congestion — Reroute Shipments",
        description="When port congestion is HIGH and active shipments are in transit, auto-generate rerouting recommendation and notify logistics team.",
        category="logistics",
        trigger=PlaybookTrigger(
            disruption_type="logistics",
            min_severity="high",
            requires_active_shipment=True,
        ),
        actions=[
            PlaybookAction(
                action_type="reroute",
                description="Identify alternate port/transshipment hub for affected shipments",
                urgency="immediate",
                target="logistics",
            ),
            PlaybookAction(
                action_type="notify_procurement",
                description="Alert procurement team of potential ETA extension (7-14 days)",
                urgency="within_24h",
                target="procurement",
            ),
            PlaybookAction(
                action_type="increase_safety_stock",
                description="Pre-release safety stock to cover extended transit window",
                urgency="within_24h",
                target="procurement",
            ),
        ],
    ),
    # 2. Quality Hold — Alt Supplier
    Playbook(
        id="pb_quality_hold_alt_supplier",
        name="Quality Hold — Qualify Alternate Supplier",
        description="When a quality issue is detected at HIGH severity, qualify alternate supplier and halt orders from affected source.",
        category="operations",
        trigger=PlaybookTrigger(
            disruption_type="operations",
            min_severity="high",
        ),
        actions=[
            PlaybookAction(
                action_type="halt_orders",
                description="Freeze all pending purchase orders from affected supplier",
                urgency="immediate",
                target="procurement",
            ),
            PlaybookAction(
                action_type="qualify_alt_supplier",
                description="Begin fast-track qualification of backup supplier from approved vendor list",
                urgency="within_24h",
                target="procurement",
            ),
            PlaybookAction(
                action_type="notify_procurement",
                description="Issue quality alert bulletin to receiving warehouses",
                urgency="immediate",
                target="logistics",
            ),
        ],
    ),
    # 3. Natural Disaster Emergency (lowered to HIGH for demo visibility)
    Playbook(
        id="pb_natural_disaster_emergency",
        name="Natural Disaster — Emergency Response",
        description="When a natural disaster impacts the supply network at HIGH+ severity, trigger emergency buffer release and executive escalation.",
        category="natural_disaster",
        trigger=PlaybookTrigger(
            disruption_type="natural_disaster",
            min_severity="high",
        ),
        actions=[
            PlaybookAction(
                action_type="increase_safety_stock",
                description="Trigger emergency buffer stock release for all affected production lines",
                urgency="immediate",
                target="procurement",
            ),
            PlaybookAction(
                action_type="escalate",
                description="Escalate to executive S&OP war-room for daily risk monitoring",
                urgency="immediate",
                target="executive",
            ),
            PlaybookAction(
                action_type="qualify_alt_supplier",
                description="Immediately qualify alternate suppliers for impacted SKUs",
                urgency="within_24h",
                target="procurement",
            ),
        ],
    ),
    # 4. Customs Delay Expedite
    Playbook(
        id="pb_customs_delay_expedite",
        name="Customs Delay — Expedite Clearance",
        description="When logistics delays hit MEDIUM+ with low inventory buffer, expedite customs and prepare alternate transport.",
        category="logistics",
        trigger=PlaybookTrigger(
            disruption_type="logistics",
            min_severity="medium",
            requires_low_buffer=True,
            buffer_threshold=5,
        ),
        actions=[
            PlaybookAction(
                action_type="reroute",
                description="Engage customs broker for expedited clearance processing",
                urgency="immediate",
                target="logistics",
            ),
            PlaybookAction(
                action_type="notify_procurement",
                description="Prepare contingent air freight mode shift if delay exceeds 72 hours",
                urgency="within_24h",
                target="logistics",
            ),
        ],
    ),
    # 5. Supplier Financial Risk
    Playbook(
        id="pb_supplier_financial_risk",
        name="Financial Risk — Dual-Source Immediately",
        description="When a supplier's financial instability reaches HIGH severity, dual-source immediately to reduce exposure.",
        category="financial",
        trigger=PlaybookTrigger(
            disruption_type="financial",
            min_severity="high",
        ),
        actions=[
            PlaybookAction(
                action_type="qualify_alt_supplier",
                description="Activate approved backup supplier and split future POs 60/40",
                urgency="immediate",
                target="procurement",
            ),
            PlaybookAction(
                action_type="halt_orders",
                description="Cap exposure: no new POs exceeding $50K until financial review complete",
                urgency="immediate",
                target="procurement",
            ),
            PlaybookAction(
                action_type="escalate",
                description="Flag for CFO review in next weekly risk council",
                urgency="next_cycle",
                target="executive",
            ),
        ],
    ),
    # 6. Production Halt — Safety Stock
    Playbook(
        id="pb_production_halt_safety_stock",
        name="Production Halt — Release Safety Stock",
        description="When operations halt at HIGH severity, release safety stock and reschedule production to preserve constrained materials.",
        category="operations",
        trigger=PlaybookTrigger(
            disruption_type="operations",
            min_severity="high",
            requires_active_shipment=True,
        ),
        actions=[
            PlaybookAction(
                action_type="increase_safety_stock",
                description="Release safety stock buffer for affected production lines",
                urgency="immediate",
                target="procurement",
            ),
            PlaybookAction(
                action_type="notify_procurement",
                description="Reschedule non-critical production to preserve constrained materials",
                urgency="within_24h",
                target="procurement",
            ),
        ],
    ),
    # 7. Cyber Incident — Isolate
    Playbook(
        id="pb_cyber_incident_isolate",
        name="Cyber Incident — Isolate & Manual Fallback",
        description="When a security incident is detected at HIGH severity, isolate digital systems and switch to manual processes.",
        category="security",
        trigger=PlaybookTrigger(
            disruption_type="security",
            min_severity="high",
        ),
        actions=[
            PlaybookAction(
                action_type="halt_orders",
                description="Suspend all automated EDI/API integrations with affected supplier",
                urgency="immediate",
                target="procurement",
            ),
            PlaybookAction(
                action_type="escalate",
                description="Notify CISO and activate incident response plan",
                urgency="immediate",
                target="executive",
            ),
            PlaybookAction(
                action_type="notify_procurement",
                description="Switch to manual PO/invoice processing via secure email",
                urgency="within_24h",
                target="procurement",
            ),
        ],
    ),
    # 8. Capacity Constraint — Rebalance
    Playbook(
        id="pb_capacity_constraint_rebalance",
        name="Capacity Constraint — Rebalance Network",
        description="When operations capacity is constrained at MEDIUM+ severity, redistribute load across the supply network.",
        category="operations",
        trigger=PlaybookTrigger(
            disruption_type="operations",
            min_severity="medium",
        ),
        actions=[
            PlaybookAction(
                action_type="reroute",
                description="Redistribute production load to underutilized facilities in the network",
                urgency="within_24h",
                target="logistics",
            ),
            PlaybookAction(
                action_type="notify_procurement",
                description="Review purchase order split across primary and secondary suppliers",
                urgency="next_cycle",
                target="procurement",
            ),
        ],
    ),
]


class PlaybookEngine:
    """Rule-based playbook engine with thread-safe mutations.

    🔴 Critical Fix #1: asyncio.Lock() on all mutations.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Deep-copy built-in playbooks so toggles don't affect the constant
        self._playbooks: dict[str, Playbook] = {
            pb.id: pb.model_copy(deep=True) for pb in BUILT_IN_PLAYBOOKS
        }
        self._executions: dict[str, PlaybookExecution] = {}
        self._feedback_service = None  # Lazy init to avoid circular imports

    def _get_feedback_service(self):
        """Lazy-load FeedbackService to avoid circular imports."""
        if self._feedback_service is None:
            from app.services.feedback_service import FeedbackService
            self._feedback_service = FeedbackService()
        return self._feedback_service

    # -------------------------------------------------------------------
    # Playbook evaluation (called as background task — 🔴 Fix #2)
    # -------------------------------------------------------------------

    async def evaluate_risk(
        self,
        risk: RiskAssessment,
        node_context: Optional[NodeContext] = None,
        node_id: str = "",
        node_name: str = "",
    ) -> list[PlaybookExecution]:
        """Evaluate a risk against all enabled playbooks.

        Returns list of triggered PlaybookExecutions.
        Called as a background task — does NOT block ingest.
        """
        triggered: list[PlaybookExecution] = []

        risk_severity_level = SEVERITY_ORDER.get(risk.severity, 0)

        for playbook in self._playbooks.values():
            if not playbook.enabled:
                continue

            trigger = playbook.trigger

            # Check disruption type match
            if trigger.disruption_type != risk.disruption_type:
                continue

            # Check severity threshold (single comparison, no bugs)
            trigger_level = SEVERITY_ORDER.get(trigger.min_severity, 0)
            if risk_severity_level < trigger_level:
                continue

            # Check context-aware conditions
            if trigger.requires_active_shipment and node_context:
                if len(node_context.active_shipments) == 0:
                    continue

            if trigger.requires_low_buffer and node_context:
                if node_context.days_buffer is not None and node_context.days_buffer > trigger.buffer_threshold:
                    continue

            # All conditions met — trigger playbook
            execution = PlaybookExecution(
                execution_id=f"exec_{uuid.uuid4().hex[:12]}",
                playbook_id=playbook.id,
                playbook_name=playbook.name,
                risk_id=risk.risk_id,
                node_id=node_id or risk.metadata.get("node_id", ""),
                node_name=node_name or risk.metadata.get("supplier", "Unknown"),
                supplier=risk.metadata.get("email_supplier", risk.metadata.get("supplier", "")),
                severity=risk.severity,
                disruption_type=risk.disruption_type,
                actions=playbook.actions,
            )

            async with self._lock:
                self._executions[execution.execution_id] = execution

            # Record trigger in feedback stats for accurate counts
            try:
                from app.services.feedback_service import FeedbackService
                feedback_svc = self._get_feedback_service()
                feedback_svc.record_trigger(playbook.id)
            except Exception:
                pass  # Non-critical — don't block execution

            triggered.append(execution)
            logger.info(
                f"Playbook triggered: '{playbook.name}' for risk {risk.risk_id} "
                f"on node {execution.node_id} (severity: {risk.severity})"
            )

        return triggered

    async def simulate_playbook(
        self,
        playbook_id: str,
        node_id: str,
        node_name: str,
        risk_score: float,
    ) -> Optional[PlaybookExecution]:
        """Simulate a playbook against a specific node.

        Creates a synthetic execution for demo purposes.
        """
        playbook = self._playbooks.get(playbook_id)
        if not playbook:
            return None

        execution = PlaybookExecution(
            execution_id=f"sim_{uuid.uuid4().hex[:12]}",
            playbook_id=playbook.id,
            playbook_name=playbook.name,
            risk_id=f"simulated_{uuid.uuid4().hex[:8]}",
            node_id=node_id,
            node_name=node_name,
            severity=playbook.trigger.min_severity,
            disruption_type=playbook.trigger.disruption_type,
            actions=playbook.actions,
            is_simulation=True,
        )

        async with self._lock:
            self._executions[execution.execution_id] = execution

        logger.info(f"Playbook simulated: '{playbook.name}' on node {node_id}")
        return execution

    # -------------------------------------------------------------------
    # Playbook CRUD
    # -------------------------------------------------------------------

    def get_playbooks(self) -> list[PlaybookWithStats]:
        """Get all playbooks enriched with stats from FeedbackService.

        ⚠️ Architecture: acceptance_rate is ALWAYS fetched from FeedbackService,
        never cached on the Playbook model.
        """
        feedback = self._get_feedback_service()
        all_stats = feedback.get_all_stats()
        stats_map = {s.playbook_id: s for s in all_stats}

        result: list[PlaybookWithStats] = []
        for pb in self._playbooks.values():
            stats = stats_map.get(pb.id)
            result.append(
                PlaybookWithStats(
                    id=pb.id,
                    name=pb.name,
                    description=pb.description,
                    trigger=pb.trigger,
                    actions=pb.actions,
                    enabled=pb.enabled,
                    category=pb.category,
                    times_triggered=stats.total_executions if stats else 0,
                    acceptance_rate=stats.acceptance_rate if stats else None,
                    last_triggered=stats.last_triggered if stats else None,
                )
            )
        return result

    async def toggle_playbook(self, playbook_id: str, enabled: bool) -> Optional[Playbook]:
        """Toggle a playbook's enabled state.

        ⚠️ Note: This is in-memory only. State resets on server restart.
        UI displays a warning about this.
        """
        async with self._lock:
            playbook = self._playbooks.get(playbook_id)
            if playbook:
                playbook.enabled = enabled
                logger.info(f"Playbook '{playbook.name}' {'enabled' if enabled else 'disabled'}")
                return playbook
        return None

    def get_executions(self) -> list[PlaybookExecution]:
        """Get all playbook executions, most recent first."""
        return sorted(
            self._executions.values(),
            key=lambda e: e.triggered_at,
            reverse=True,
        )

    def get_execution(self, execution_id: str) -> Optional[PlaybookExecution]:
        """Get a single execution by ID."""
        return self._executions.get(execution_id)

    async def evaluate_risks(
        self, risks: list[RiskAssessment]
    ) -> list[PlaybookExecution]:
        """Evaluate a list of risks against all enabled playbooks.

        Convenience wrapper around evaluate_risk() for batch processing.
        Returns all triggered executions across all risks.
        """
        all_triggered: list[PlaybookExecution] = []
        for risk in risks:
            triggered = await self.evaluate_risk(risk)
            all_triggered.extend(triggered)
        return all_triggered

    async def update_execution_status(
        self, execution_id: str, status: str, feedback: Optional[str] = None
    ) -> Optional[PlaybookExecution]:
        """Update an execution's status after user feedback."""
        async with self._lock:
            execution = self._executions.get(execution_id)
            if execution:
                execution.status = status
                execution.user_feedback = feedback
                return execution
        return None
