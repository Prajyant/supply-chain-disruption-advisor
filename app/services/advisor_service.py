from __future__ import annotations
from app.ingestion.loaders import load_all_data
from app.models.schemas import ChatResponse, IngestResponse, RetrievedContext, RiskAssessment
from app.retrieval.index import RetrievalIndex
from app.services.risk_engine import RiskAnalyzer


class AdvisorService:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.risks: list[RiskAssessment] = []
        self.index = RetrievalIndex()
        self.analyzer = RiskAnalyzer()

    def ingest(
        self,
        supplier_emails_path: str,
        news_feed_path: str,
        inventory_path: str,
        use_realtime_news: bool = True,
    ) -> IngestResponse:
        self.events = load_all_data(
            supplier_emails_path=supplier_emails_path,
            news_feed_path=news_feed_path,
            inventory_path=inventory_path,
            use_realtime_news=use_realtime_news,
        )
        self.index.build(self.events)
        self.risks = [self.analyzer.analyze_event(event) for event in self.events]
        self.risks.sort(
            key=lambda r: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(r.severity, 0),
            reverse=True,
        )
        msg = "Real-time data fetched from WorldMonitor API." if use_realtime_news else "Data ingested and risks assessed."
        return IngestResponse(
            ingested_events=len(self.events),
            indexed_chunks=self.index.chunk_count,
            message=msg,
        )

    def get_risks(self) -> list[RiskAssessment]:
        return self.risks

    def chat(self, question: str, top_k: int = 5) -> ChatResponse:
        contexts = self.index.query(question=question, top_k=top_k)
        answer, recommendations = self.analyzer.answer_question(question=question, contexts=contexts)
        return ChatResponse(
            answer=answer,
            supporting_context=contexts,
            recommendations=recommendations,
        )

    def _to_retrieved_contexts(self, contexts: list[dict]) -> list[RetrievedContext]:
        return [RetrievedContext(**c) for c in contexts]
