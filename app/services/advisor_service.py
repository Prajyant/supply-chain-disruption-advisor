"""Advisor service that orchestrates all services."""
from __future__ import annotations
import logging
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
    ) -> IngestResponse:
        """Ingest data from multiple sources.

        Args:
            supplier_emails_path: Path to supplier emails CSV
            news_feed_path: Path to news feed CSV
            inventory_path: Path to inventory CSV
            use_realtime_news: Whether to fetch real-time news

        Returns:
            Ingestion response with statistics
        """
        result = self.ingestion_service.ingest(
            supplier_emails_path=supplier_emails_path,
            news_feed_path=news_feed_path,
            inventory_path=inventory_path,
            use_realtime_news=use_realtime_news,
        )

        # Set up chat service with the new index
        index = self.ingestion_service.get_index()
        if index:
            self.chat_service.set_index(index)

        return IngestResponse(
            ingested_events=result["ingested_events"],
            indexed_chunks=result["indexed_chunks"],
            message=result["message"],
        )

    def get_risks(self) -> list[RiskAssessment]:
        """Get all risk assessments.

        Returns:
            List of risk assessments
        """
        # Get risks from risk service
        risks = self.risk_service.get_risks()

        # If no risks, return empty list
        if not risks:
            return []

        # Sort by severity
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        risks.sort(
            key=lambda r: severity_order.get(r.get("severity", "low"), 0),
            reverse=True,
        )

        # Convert to RiskAssessment models
        return [RiskAssessment(**r) for r in risks]

    def chat(self, question: str, top_k: int = 5) -> ChatResponse:
        """Query the AI advisor.

        Args:
            question: The user's question
            top_k: Number of relevant chunks to retrieve

        Returns:
            Chat response with answer and context
        """
        result = self.chat_service.chat(question, top_k)

        # Convert supporting context to RetrievedContext models
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
        """Get the supply chain network graph.

        Returns:
            Network graph data
        """
        return self.graph_service.get_network()

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get details for a specific node.

        Args:
            node_id: The node ID

        Returns:
            Node details or None
        """
        return self.graph_service.get_node(node_id)

    def propagate_risk(self) -> dict:
        """Trigger risk propagation through the graph.

        Returns:
            Propagation results
        """
        return self.graph_service.propagate_risk()
