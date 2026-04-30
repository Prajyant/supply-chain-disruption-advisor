"""Advisor service that orchestrates all services."""
from __future__ import annotations
import asyncio
import logging
import re
from typing import Any, Optional

from app.models.schemas import ChatResponse, IngestResponse, RetrievedContext, RiskAssessment
from app.services.ingestion_service import IngestionService
from app.services.risk_service import RiskService
from app.services.chat_service import ChatService
from app.services.graph_service import GraphService
from app.services.shipment_tracker import ShipmentTracker, ShipmentStatus
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

# Location keywords for news → node matching (shared with risk_engine)
LOCATION_KEYWORDS: dict[str, list[str]] = {
    "shanghai": ["shanghai", "china", "chinese"],
    "taipei": ["taipei", "taiwan", "taiwanese"],
    "tokyo": ["tokyo", "japan", "japanese"],
    "busan": ["busan", "korea", "korean"],
    "los angeles": ["los angeles", "la port", "long beach", "west coast"],
    "rotterdam": ["rotterdam", "netherlands", "dutch"],
    "guangzhou": ["guangzhou", "guangdong", "south china"],
    "ho chi minh": ["ho chi minh", "vietnam", "vietnamese"],
    "gujarat": ["gujarat", "india", "indian", "mundra"],
    "newark": ["newark", "new jersey", "east coast"],
    "detroit": ["detroit", "michigan"],
    "chicago": ["chicago", "midwest", "illinois"],
    "seoul": ["seoul", "south korea"],
}


class AdvisorService:
    """Main service that orchestrates all supply chain disruption advisor services."""

    def __init__(self) -> None:
        self.ingestion_service = IngestionService()
        self.risk_service = RiskService()
        self.chat_service = ChatService()
        self.graph_service = GraphService()
        self.shipment_tracker = ShipmentTracker()

        # Cached data for context enrichment (populated at ingest time)
        self._cached_news_events: list[dict] = []
        self._cached_inventory_data: list[dict] = []
        self._cached_email_events: list[dict] = []

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

        # Cache for context enrichment
        self._cached_news_events = news_events
        self._cached_email_events = email_events

        logger.info(
            f"Separated {len(email_events)} operational emails and "
            f"{len(news_events)} news events for cross-reference"
        )

        # ---------------------------------------------------------------
        # STEP 2: Reactive layer — analyze emails/inventory only
        # News events are context for Gemini, NOT individual risk assessments
        # ---------------------------------------------------------------
        all_risks = self.risk_service.analyze_events(email_events)

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

        # ---------------------------------------------------------------
        # STEP 5: Ingest shipments + process status updates (sync wrapper)
        # ---------------------------------------------------------------
        self._process_shipments_sync(email_events)

        # ---------------------------------------------------------------
        # STEP 6: Update context summary cache (lightweight, at ingest time)
        # ---------------------------------------------------------------
        self._update_context_caches(all_risks, predictions)

        # Count predictions for the response message
        pred_count = len(predictions)

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

    def _process_shipments_sync(self, email_events: list[dict]) -> None:
        """Ingest shipments and process status updates synchronously.

        Uses the ShipmentTracker's internal methods directly (bypassing the
        async lock wrapper) since we're already in a sync context during
        ingestion. The lock protects concurrent HTTP requests, not this
        single-threaded ingestion path.
        """
        try:
            # Ingest initial shipments from emails
            created = 0
            for event in email_events:
                shipment = self.shipment_tracker._parse_shipment_from_event(event)
                if shipment:
                    self.shipment_tracker._shipments[shipment.id] = shipment
                    if shipment.tracking_number:
                        self.shipment_tracker._tracking_index[shipment.tracking_number.lower()] = shipment.id
                    supplier_key = shipment.supplier.lower().strip()
                    if supplier_key not in self.shipment_tracker._supplier_index:
                        self.shipment_tracker._supplier_index[supplier_key] = []
                    if shipment.id not in self.shipment_tracker._supplier_index[supplier_key]:
                        self.shipment_tracker._supplier_index[supplier_key].append(shipment.id)
                    created += 1

            logger.info(f"ShipmentTracker sync-ingested {created} shipments from {len(email_events)} events")

            # Load and process follow-up status updates
            update_events = self.shipment_tracker.load_shipment_updates_csv()
            if update_events:
                # Ingest update events as shipments too
                for event in update_events:
                    shipment = self.shipment_tracker._parse_shipment_from_event(event)
                    if shipment:
                        self.shipment_tracker._shipments[shipment.id] = shipment
                        if shipment.tracking_number:
                            self.shipment_tracker._tracking_index[shipment.tracking_number.lower()] = shipment.id
                        supplier_key = shipment.supplier.lower().strip()
                        if supplier_key not in self.shipment_tracker._supplier_index:
                            self.shipment_tracker._supplier_index[supplier_key] = []
                        if shipment.id not in self.shipment_tracker._supplier_index[supplier_key]:
                            self.shipment_tracker._supplier_index[supplier_key].append(shipment.id)

                # Process status changes
                for event in update_events:
                    result = self.shipment_tracker._process_single_update(event)
                    if result:
                        # Update graph node risk score
                        if result.risk_score_change is not None:
                            self._map_to_graph(result.supplier, result.risk_score_change)
                        logger.info(
                            f"Shipment {result.shipment_id}: {result.old_status} → {result.new_status}"
                        )

        except Exception as e:
            logger.error(f"Shipment processing failed: {e}", exc_info=True)

    def _update_context_caches(
        self, reactive_risks: list[dict], predictions: list[RiskAssessment]
    ) -> None:
        """Precompute lightweight context summaries per node.

        Called at ingest time — NOT inside get_network().
        """
        # Count risks per supplier
        risk_counts: dict[str, int] = {}
        has_critical: dict[str, bool] = {}

        for risk in reactive_risks:
            supplier = (
                risk.get("metadata", {}).get("sender_name")
                or risk.get("supplier", "")
            ).lower()
            if supplier and risk.get("severity") != "low":
                risk_counts[supplier] = risk_counts.get(supplier, 0) + 1
                if risk.get("severity") == "critical":
                    has_critical[supplier] = True

        for pred in predictions:
            supplier = pred.metadata.get("email_supplier", "").lower()
            if supplier:
                risk_counts[supplier] = risk_counts.get(supplier, 0) + 1
                if pred.severity == "critical":
                    has_critical[supplier] = True

        # Update cache for each graph node
        for node_id, node in self.graph_service.graph.nodes.items():
            node_name_lower = node.name.lower()
            shipment_count = self.shipment_tracker.get_shipment_count_for_supplier(node.name)
            rc = risk_counts.get(node_name_lower, 0)
            hc = has_critical.get(node_name_lower, False)

            self.graph_service.update_context_cache(
                node_id=node_id,
                shipment_count=shipment_count,
                risk_count=rc,
                has_critical_risk=hc,
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

    def _resolve_node_id(self, supplier_name: str) -> Optional[str]:
        """Resolve a supplier name to a graph node ID."""
        node_id = "live_" + re.sub(r"[^a-z0-9]", "_", supplier_name.lower())[:30]
        if self.graph_service.graph.get_node(node_id):
            return node_id
        # Try static nodes
        for nid, n in self.graph_service.graph.nodes.items():
            if supplier_name.lower() in n.name.lower():
                return nid
        return None

    def get_risks(self) -> list[RiskAssessment]:
        """Get all risk assessments (reactive + predictive).

        Returns:
            - Predictive risks (from Gemini cross-reference) — always shown
            - Reactive risks from emails that self-reported a problem (medium/high/critical)
            - Low-severity routine emails are suppressed — they are operational noise
        """
        reactive_risks = self.risk_service.get_risks()
        predictions = self.risk_service.get_predictions()

        all_risks: list[dict] = []

        # Add predictions (always shown — this is the main value-add)
        for pred in predictions:
            all_risks.append(pred.model_dump())

        # Add reactive email risks — only those that actually flagged a problem
        for risk in reactive_risks:
            meta = risk.get("metadata", {}) or {}
            # Skip news context placeholders
            if meta.get("_news_context_only"):
                continue
            # Skip low-severity routine operational emails (they have no problem to report)
            if risk.get("severity") == "low":
                continue
            all_risks.append(risk)

        if not all_risks:
            return []

        # Sort: predictions first, then by severity descending
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        def sort_key(r: dict) -> tuple:
            is_pred = 1 if r.get("metadata", {}).get("type") == "prediction" else 0
            sev = severity_order.get(r.get("severity", "low"), 0)
            return (is_pred, sev)

        all_risks.sort(key=sort_key, reverse=True)
        return [RiskAssessment(**r) for r in all_risks]

    def get_node_context(self, node_id: str) -> Optional[dict]:
        """Get full enriched context for a node (called on node click).

        Enriches the graph_service base context with:
        - Active shipments from ShipmentTracker
        - Pending orders from cached inventory
        - Risk history from RiskService
        - Connected news (top 3 by relevance, threshold > 0.6)
        - days_buffer calculation
        """
        context = self.graph_service.get_node_context(node_id)
        if not context:
            return None

        node_name = context["name"]

        # Enrich with shipments
        context["active_shipments"] = self.shipment_tracker.get_shipments_for_node(
            node_id, node_name
        )

        # Enrich with pending orders from inventory
        context["pending_orders"] = self._get_orders_for_node(node_name)

        # Enrich with risk history
        context["risk_history"] = self._get_risk_history_for_node(node_name)

        # Enrich with connected news (top 3, relevance > 0.6)
        context["connected_news"] = self._get_news_for_node(
            context["location"], node_name
        )

        # Calculate days_buffer from inventory
        context["days_buffer"] = self._calc_days_buffer(node_name)

        return context

    def _get_orders_for_node(self, node_name: str) -> list[dict]:
        """Get pending orders from cached inventory data."""
        orders = []
        for event in self._cached_email_events:
            meta = event.get("metadata", {}) or {}
            supplier = (
                event.get("supplier", "")
                or meta.get("sender_name", "")
            )
            if not supplier or node_name.lower() not in supplier.lower():
                if supplier.lower() not in node_name.lower():
                    continue
            material = meta.get("material", "")
            if material:
                orders.append({
                    "order_id": event.get("reference_id", ""),
                    "supplier": supplier,
                    "material": material,
                    "quantity": 0,
                    "status": "pending",
                    "expected_date": meta.get("date", ""),
                })
        return orders

    def _get_risk_history_for_node(self, node_name: str) -> list[dict]:
        """Get risk history for a node from RiskService."""
        all_risks = self.risk_service.get_risks()
        history = []
        for risk in all_risks:
            meta = risk.get("metadata", {}) or {}
            supplier = meta.get("sender_name", "")
            if not supplier:
                continue
            if node_name.lower() in supplier.lower() or supplier.lower() in node_name.lower():
                if risk.get("severity", "low") != "low":
                    history.append({
                        "risk_id": risk.get("risk_id", ""),
                        "severity": risk.get("severity", "low"),
                        "disruption_type": risk.get("disruption_type", ""),
                        "detected_at": risk.get("detected_at", ""),
                        "summary": risk.get("summary", ""),
                        "source": risk.get("source", ""),
                    })
        return history

    def _get_news_for_node(self, node_location: str, node_name: str) -> list[dict]:
        """Get connected news articles for a node.

        Caps at top 3 by relevance score, threshold > 0.6.
        """
        scored_news: list[tuple[float, dict]] = []

        node_loc_lower = node_location.lower()
        # Find which location keywords match this node
        node_loc_keys = set()
        for loc, kws in LOCATION_KEYWORDS.items():
            if any(kw in node_loc_lower for kw in kws):
                node_loc_keys.add(loc)

        if not node_loc_keys:
            return []

        for event in self._cached_news_events:
            news_text = str(event.get("text", "")).lower()
            meta = event.get("metadata", {}) or {}

            # Calculate relevance score based on keyword overlap
            matches = 0
            total_keywords = 0
            for loc in node_loc_keys:
                kws = LOCATION_KEYWORDS.get(loc, [])
                total_keywords += len(kws)
                matches += sum(1 for kw in kws if kw in news_text)

            if total_keywords == 0:
                continue
            relevance = min(1.0, matches / max(1, len(node_loc_keys)))

            if relevance > 0.6:
                headline = meta.get("title", "") or event.get("text", "")[:80]
                scored_news.append((relevance, {
                    "news_id": event.get("reference_id", ""),
                    "headline": headline,
                    "region": meta.get("region", ""),
                    "date": meta.get("date", event.get("event_time", "")),
                    "relevance_score": round(relevance, 2),
                }))

        # Sort by relevance descending, cap at 3
        scored_news.sort(key=lambda x: x[0], reverse=True)
        return [n[1] for n in scored_news[:3]]

    def _calc_days_buffer(self, node_name: str) -> Optional[int]:
        """Calculate days_buffer: (current_stock - safety_stock) / daily_consumption."""
        for event in self._cached_email_events:
            if event.get("source") != "inventory":
                continue
            meta = event.get("metadata", {}) or {}
            supplier = meta.get("primary_supplier", "")
            if supplier and (
                node_name.lower() in supplier.lower()
                or supplier.lower() in node_name.lower()
            ):
                stock = float(meta.get("current_stock", 0) or 0)
                reorder = float(meta.get("reorder_point", 0) or 0)
                days_cover = int(meta.get("days_of_cover", 0) or 0)
                if days_cover > 0 and stock > 0:
                    daily = stock / days_cover
                    if daily > 0:
                        return max(0, int((stock - reorder) / daily))
        return None

    def get_shipments(self) -> list[dict]:
        """Get all tracked shipments."""
        return self.shipment_tracker.get_all_shipments()

    def get_shipments_for_node(self, node_id: str) -> list[dict]:
        """Get shipments for a specific node."""
        node = self.graph_service.get_node(node_id)
        node_name = node.get("name", "") if node else ""
        return self.shipment_tracker.get_shipments_for_node(node_id, node_name)

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
