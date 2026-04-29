"""Advisor service that orchestrates all services."""
from __future__ import annotations
import logging
import re
from typing import Optional

from app.models.schemas import ChatResponse, IngestResponse, RetrievedContext, RiskAssessment
from app.services.ingestion_service import IngestionService
from app.services.risk_service import RiskService
from app.services.chat_service import ChatService
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)


class AdvisorService:
    """Main service that orchestrates all supply chain disruption advisor services."""

    def __init__(self) -> None:
        self.ingestion_service = IngestionService()
        self.risk_service = RiskService()
        self.chat_service = ChatService()
        self.graph_service = GraphService()

        # Load sample graph
        self.graph_service.load_sample_graph()

    def ingest(
        self,
        supplier_emails_path: str,
        news_feed_path: str,
        inventory_path: str,
        use_realtime_news: bool = True,
        use_live_emails: bool = False,
    ) -> IngestResponse:
        """Ingest data from multiple sources, then run predictive cross-reference.

        The key innovation: instead of scanning each event individually,
        we SEPARATE emails from news, then cross-reference them to predict
        which normal operations might be disrupted by current world events.
        """
        result = self.ingestion_service.ingest(
            supplier_emails_path=supplier_emails_path,
            news_feed_path=news_feed_path,
            inventory_path=inventory_path,
            use_realtime_news=use_realtime_news,
            use_live_emails=use_live_emails,
        )

        # Set up chat service with the new index
        index = self.ingestion_service.get_index()
        if index:
            self.chat_service.set_index(index)

        events = result.get("events", [])

        # ---------------------------------------------------------------
        # STEP 1: Separate emails (operations) from news
        # ---------------------------------------------------------------
        email_events = [
            e for e in events
            if e.get("source") in ("supplier_email", "live_email", "inventory")
        ]
        news_events = [
            e for e in events
            if e.get("source") not in ("supplier_email", "live_email", "inventory")
        ]

        logger.info(
            f"Separated {len(email_events)} operational emails and "
            f"{len(news_events)} news events for cross-reference"
        )

        # ---------------------------------------------------------------
        # STEP 2: Run individual analysis on each event (reactive layer)
        # ---------------------------------------------------------------
        all_risks = self.risk_service.analyze_events(events)

        # ---------------------------------------------------------------
        # STEP 3: Run PREDICTIVE cross-reference (the magic)
        # ---------------------------------------------------------------
        predictions = self.risk_service.cross_reference(email_events, news_events)

        # ---------------------------------------------------------------
        # STEP 4: Map all risks to the Digital Twin graph
        # ---------------------------------------------------------------
        score_map = {"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.3}

        # Map reactive risks
        for risk in all_risks:
            supplier_name = (
                risk.get("metadata", {}).get("sender_name")
                or risk.get("metadata", {}).get("supplier")
                or risk.get("supplier")
                or "Unknown Supplier"
            )
            severity = risk.get("severity", "low")
            score = score_map.get(severity, 0.3)
            self._map_to_graph(supplier_name, score)

        # Map predictive risks
        for pred in predictions:
            supplier_name = pred.metadata.get("email_supplier", "Unknown")
            score = score_map.get(pred.severity, 0.3)
            self._map_to_graph(supplier_name, score)

        # Count predictions for the response message
        pred_count = len(predictions)
        reactive_count = len(all_risks)

        message = result["message"]
        if pred_count > 0:
            message += f" 🔮 Predictive engine found {pred_count} potential disruptions by cross-referencing your operations with world news."
        else:
            message += f" ✅ No predicted disruptions found — your active operations appear safe."

        return IngestResponse(
            ingested_events=result["ingested_events"],
            indexed_chunks=result["indexed_chunks"],
            message=message,
        )

    def _map_to_graph(self, supplier_name: str, score: float) -> None:
        """Map a risk to the Digital Twin graph, creating nodes dynamically."""
        if supplier_name == "Unknown Supplier":
            return

        # Check for existing node
        node_id = "live_" + re.sub(r"[^a-z0-9]", "_", supplier_name.lower())[:30]
        existing = self.graph_service.graph.get_node(node_id)

        if not existing:
            # Try to find a static node with matching name
            existing = self.graph_service.graph.get_node(
                next(
                    (nid for nid, n in self.graph_service.graph.nodes.items()
                     if supplier_name.lower() in n.name.lower()),
                    None
                )
            )

        if existing:
            self.graph_service.set_node_direct_risk(existing.id, score)
        else:
            self.graph_service.add_or_update_node(supplier_name, score)

    def get_risks(self) -> list[RiskAssessment]:
        """Get all risk assessments (reactive + predictive).

        Returns:
            List of risk assessments sorted by severity
        """
        # Get both reactive and predictive risks
        risks = self.risk_service.get_risks()
        predictions = self.risk_service.get_predictions()

        # Combine
        all_risks = list(risks)

        # Convert predictions (already RiskAssessment objects) to dicts
        for pred in predictions:
            all_risks.append(pred.model_dump())

        if not all_risks:
            return []

        # Sort by severity
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        all_risks.sort(
            key=lambda r: severity_order.get(r.get("severity", "low"), 0),
            reverse=True,
        )

        return [RiskAssessment(**r) for r in all_risks]

    def chat(self, question: str, top_k: int = 5) -> ChatResponse:
        """Query the AI advisor."""
        result = self.chat_service.chat(question, top_k)

        contexts = [
            RetrievedContext(
                source="unknown",
                reference_id="",
                text=text,
                score=0.0,
                metadata={},
            )
            for text in result.get("supporting_context", [])
        ]

        return ChatResponse(
            answer=result.get("answer", ""),
            supporting_context=contexts,
            recommendations=result.get("recommendations", []),
        )

    def get_network(self) -> dict:
        """Get the supply chain network graph."""
        return self.graph_service.get_network()

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get details for a specific node."""
        return self.graph_service.get_node(node_id)

    def propagate_risk(self) -> dict:
        """Trigger risk propagation through the graph."""
        return self.graph_service.propagate_risk()
