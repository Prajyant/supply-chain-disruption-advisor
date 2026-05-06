"""Background job workers for periodic tasks."""
import asyncio
import logging
from typing import Optional
from datetime import datetime

from app.services.ingestion_service import IngestionService
from app.services.risk_service import RiskService
from app.services.graph_service import GraphService
from app.websocket.manager import manager

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Base class for background workers."""

    def __init__(self, interval_seconds: int) -> None:
        self.interval_seconds = interval_seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background worker."""
        if self.running:
            logger.warning("Worker already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info(f"Worker started with interval {self.interval_seconds}s")

    async def stop(self) -> None:
        """Stop the background worker."""
        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Worker stopped")

    async def _run_loop(self) -> None:
        """Run the worker loop."""
        while self.running:
            try:
                await self.run()
            except Exception as e:
                logger.error(f"Worker error: {e}")

            await asyncio.sleep(self.interval_seconds)

    async def run(self) -> None:
        """Override this method with the worker's logic."""
        raise NotImplementedError


class IngestionWorker(BackgroundWorker):
    """Worker for periodic news ingestion."""

    def __init__(
        self,
        interval_seconds: int = 900,  # 15 minutes
        ingestion_service: Optional[IngestionService] = None,
        graph_service: Optional[GraphService] = None,
    ) -> None:
        super().__init__(interval_seconds)
        self.ingestion_service = ingestion_service or IngestionService()
        self.graph_service = graph_service

    async def run(self) -> None:
        """Run the ingestion worker."""
        logger.info("Running ingestion worker...")

        try:
            # Run blocking ingestion in a thread to avoid stalling the event loop
            result = await asyncio.to_thread(
                self.ingestion_service.ingest,
                supplier_emails_path="data/supplier_emails.csv",
                news_feed_path="data/news_feed.csv",
                inventory_path="data/inventory.csv",
                use_realtime_news=True,
            )

            logger.info(f"Ingestion complete: {result}")

            # Populate the ShipmentTracker from email events
            events = result.get("events", [])
            email_events = [
                e for e in events
                if e.get("source") in ("supplier_email", "live_email", "inventory")
            ]
            news_events = [
                e for e in events
                if e.get("source") not in ("supplier_email", "live_email", "inventory")
            ]

            if email_events:
                await self._populate_shipment_tracker(email_events)

            # Run risk analysis and map to Digital Twin graph
            await self._analyze_and_map_risks(email_events, news_events)

            # Broadcast completion
            await manager.broadcast_ingestion_complete(
                events_count=result.get("ingested_events", 0),
                risks_count=result.get("indexed_chunks", 0),
            )
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")

    async def _populate_shipment_tracker(self, email_events: list) -> None:
        """Populate the ShipmentTracker singleton from ingested email events."""
        try:
            from app.services.shipment_tracker import ShipmentTracker
            tracker = ShipmentTracker()
            created = await tracker.ingest_shipments(email_events)

            # Also load status updates CSV
            update_events = tracker.load_shipment_updates_csv()
            if update_events:
                await tracker.ingest_shipments(update_events)
                await tracker.process_status_updates(update_events)

            logger.info(f"Background worker populated ShipmentTracker with {created} shipments")
        except Exception as e:
            logger.error(f"ShipmentTracker population failed: {e}")

    async def _analyze_and_map_risks(self, email_events: list, news_events: list) -> None:
        """Run risk analysis on events and map results to the Digital Twin graph."""
        if not self.graph_service:
            logger.warning("No GraphService available for risk mapping")
            return
        try:
            graph_service = self.graph_service

            # Score graph nodes using live weather/trade intelligence
            from app.ingestion.weather_monitor import fetch_weather_events
            from app.ingestion.trade_monitor import fetch_trade_policy_events

            severity_map = {"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.2}
            weather_events = await asyncio.to_thread(fetch_weather_events, 20)
            trade_events = await asyncio.to_thread(fetch_trade_policy_events, 15)

            scored = 0
            for node in graph_service.graph.nodes.values():
                node_name = node.name.lower()
                node_location = node.location.lower()
                max_risk = node.direct_risk

                for event in weather_events:
                    meta = event.get("metadata", {})
                    event_loc = str(meta.get("location", "")).lower()
                    if event_loc and (event_loc in node_name or event_loc in node_location or node_name in event_loc):
                        risk = severity_map.get(meta.get("severity", "low"), 0.2)
                        max_risk = max(max_risk, risk)

                for event in trade_events:
                    text = event.get("text", "").lower()
                    meta = event.get("metadata", {})
                    if node_name in text or node_location in text:
                        risk = severity_map.get(meta.get("severity", "low"), 0.2)
                        max_risk = max(max_risk, risk)

                if max_risk > node.direct_risk:
                    node.direct_risk = max_risk
                    scored += 1

            # Propagate risk through the graph
            prop_result = graph_service.propagate_risk()
            logger.info(
                "Graph risk scoring: %d nodes scored, propagation updated %d nodes",
                scored, len(prop_result.get("updated_nodes", [])),
            )

            # --- Update global chat context ---
            await self._update_chat_global_context(weather_events, trade_events)

        except Exception as e:
            logger.error(f"Risk analysis/mapping failed: {e}")

    async def _update_chat_global_context(
        self, weather_events: list, trade_events: list
    ) -> None:
        """Push latest system state into the ChatService global context.

        This makes the chat advisor aware of all current risks, shipments,
        weather, trade events, and network state — regardless of which page
        the user is on.
        """
        try:
            from app.services.chat_service import ChatService
            from app.services.shipment_tracker import ShipmentTracker

            chat_service = ChatService()
            tracker = ShipmentTracker()

            # Gather risks from the ingestion service
            risks = []
            try:
                from app.services.risk_service import RiskService
                risk_svc = RiskService()
                reactive = risk_svc.get_risks()
                predictions = risk_svc.get_predictions()
                for pred in predictions:
                    risks.append(pred.model_dump() if hasattr(pred, "model_dump") else pred)
                for r in reactive:
                    meta = r.get("metadata", {}) or {}
                    if not meta.get("_news_context_only") and r.get("severity") != "low":
                        risks.append(r)
            except Exception:
                pass

            # Gather shipments
            shipments = tracker.get_all_shipments()

            # Network summary
            network_summary = {}
            if self.graph_service:
                total_nodes = len(self.graph_service.graph.nodes)
                at_risk = sum(
                    1 for n in self.graph_service.graph.nodes.values()
                    if n.direct_risk >= 0.5
                )
                network_summary = {
                    "total_nodes": total_nodes,
                    "at_risk_nodes": at_risk,
                }

            chat_service.update_global_context(
                risks=risks,
                shipments=shipments,
                weather_events=weather_events,
                trade_events=trade_events,
                network_summary=network_summary,
            )
            logger.info(
                "Chat global context updated: %d risks, %d shipments, %d weather, %d trade",
                len(risks), len(shipments), len(weather_events), len(trade_events),
            )
        except Exception as e:
            logger.error(f"Failed to update chat global context: {e}")


from app.ingestion.worldmonitor import fetch_realtime_news

class RiskWorker(BackgroundWorker):
    """Worker for periodic risk analysis."""

    def __init__(
        self,
        interval_seconds: int = 1800,  # 30 minutes
        risk_service: Optional[RiskService] = None,
    ) -> None:
        super().__init__(interval_seconds)
        self.risk_service = risk_service or RiskService()

    async def run(self) -> None:
        """Run the risk worker."""
        logger.info("Running risk worker...")

        try:
            # Fetch fresh news in a thread (blocking RSS/Weather calls)
            news = await asyncio.to_thread(fetch_realtime_news)
            
            cached_ops = self.risk_service.get_predictions()  # Use the proper getter
            if cached_ops:
                # Re-evaluate in a thread (potential heavy LLM or regex logic)
                await asyncio.to_thread(
                    self.risk_service.cross_reference,
                    [p.metadata if hasattr(p, 'metadata') else p.get('metadata', {}) for p in cached_ops], 
                    news
                )
            
            # Broadcast updates for critical risks
            for risk in self.risk_service.get_critical_risks():
                await manager.broadcast_risk_update(
                    risk_id=risk.get("risk_id", ""),
                    severity=risk.get("severity", "critical"),
                    node_id=risk.get("metadata", {}).get("node_id"),
                )
                # Send SES email for critical risks
                await self._send_risk_email(risk)
        except Exception as e:
            logger.error(f"Risk analysis failed: {e}")

    async def _send_risk_email(self, risk: dict) -> None:
        """Send SES email notification for a critical/high risk."""
        try:
            from app.services.email_service import EmailService
            from app.services.risk_engine import RECOMMENDATION_MAP
            email_service = EmailService()

            metadata = risk.get("metadata", {}) or {}
            severity = risk.get("severity", "critical")

            # Use risk recommendations if available, otherwise fall back to severity-based actions
            recommendations = risk.get("recommendations", [])
            if not recommendations:
                recommendations = RECOMMENDATION_MAP.get(severity, RECOMMENDATION_MAP.get("high", []))

            result = email_service.send_routed_alert(
                risk_severity=severity,
                risk_headline=risk.get("headline", risk.get("summary", "Supply chain risk detected")),
                supplier=metadata.get("sender_name", metadata.get("supplier", "")),
                disruption_type=risk.get("disruption_type", ""),
                recommendations=recommendations,
            )
            if result.success:
                logger.info(
                    "SES risk alert sent: severity=%s, recipients=%s",
                    risk.get("severity"), result.recipients_notified,
                )
            else:
                logger.warning("SES risk alert failed: %s", result.error)
        except Exception as e:
            logger.error(f"Risk email notification failed: {e}")


class PropagationWorker(BackgroundWorker):
    """Worker for impact propagation."""

    def __init__(
        self,
        interval_seconds: int = 60,  # 1 minute
        graph_service: Optional[GraphService] = None,
    ) -> None:
        super().__init__(interval_seconds)
        self.graph_service = graph_service or GraphService()

    async def run(self) -> None:
        """Run the propagation worker."""
        logger.info("Running propagation worker...")

        try:
            result = self.graph_service.propagate_risk()
            logger.info(f"Propagation complete: {result}")

            # Broadcast node status updates
            for node_id in result.get("updated_nodes", []):
                node = self.graph_service.get_node(node_id)
                if node:
                    await manager.broadcast_node_status(
                        node_id=node_id,
                        status=node.get("status", "normal"),
                        risk_score=node.get("risk_score", 0.0),
                    )
        except Exception as e:
            logger.error(f"Propagation failed: {e}")


class WorkerManager:
    """Manager for all background workers."""

    def __init__(self) -> None:
        self.workers: dict[str, BackgroundWorker] = {}

    def register_worker(self, name: str, worker: BackgroundWorker) -> None:
        """Register a worker.

        Args:
            name: The worker name
            worker: The worker instance
        """
        self.workers[name] = worker
        logger.info(f"Registered worker: {name}")

    async def start_all(self) -> None:
        """Start all registered workers."""
        for name, worker in self.workers.items():
            await worker.start()
            logger.info(f"Started worker: {name}")

    async def stop_all(self) -> None:
        """Stop all registered workers."""
        for name, worker in self.workers.items():
            await worker.stop()
            logger.info(f"Stopped worker: {name}")

    def get_worker(self, name: str) -> Optional[BackgroundWorker]:
        """Get a worker by name.

        Args:
            name: The worker name

        Returns:
            The worker or None
        """
        return self.workers.get(name)
