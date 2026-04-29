"""Chat service for AI-powered advisory responses."""
import logging
from typing import Optional

from app.retrieval.index import RetrievalIndex

logger = logging.getLogger(__name__)


class ChatService:
    """Service for AI-powered chat advisory."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.vector_index = None
        return cls._instance

    def __init__(self) -> None:
        pass

    def set_index(self, index: RetrievalIndex) -> None:
        """Set the vector index for retrieval.

        Args:
            index: The vector index to use
        """
        self.vector_index = index

    def chat(self, question: str, top_k: int = 5) -> dict[str, str | list]:
        """Generate a response to a user question using retrieved context.

        Args:
            question: The user's question
            top_k: Number of relevant chunks to retrieve

        Returns:
            Dictionary with answer, context, and recommendations
        """
        if not self.vector_index:
            return {
                "answer": "No data available. Please ingest data first.",
                "supporting_context": [],
                "recommendations": [],
            }

        # Retrieve relevant chunks
        contexts = self.vector_index.query(question, top_k=top_k)

        if not contexts:
            return {
                "answer": "I couldn't find relevant information in the data. Try asking about specific suppliers, disruptions, or risk types.",
                "supporting_context": [],
                "recommendations": [],
            }

        # Build context from chunks
        context = "\n\n".join([c.text for c in contexts])

        # Generate answer using heuristics
        answer = self._heuristic_answer(question, contexts)

        # Extract recommendations from context
        recommendations = self._extract_recommendations(contexts)

        return {
            "answer": answer,
            "supporting_context": [c.text for c in contexts],
            "recommendations": recommendations,
        }

    def _heuristic_answer(self, question: str, contexts: list) -> str:
        """Generate a heuristic-based answer.

        Args:
            question: The user's question
            contexts: The retrieved contexts

        Returns:
            Heuristic answer
        """
        question_lower = question.lower()

        # Count sources
        sources = {}
        for ctx in contexts:
            source = ctx.source
            sources[source] = sources.get(source, 0) + 1

        # Build answer based on question type
        if "risk" in question_lower or "disruption" in question_lower:
            total = len(contexts)
            if total > 0:
                return f"Based on the data, I found {total} relevant events related to your question. The main sources are: {', '.join(sources.keys())}."

        if "supplier" in question_lower:
            suppliers = set()
            for ctx in contexts:
                supplier = ctx.metadata.get("supplier", "")
                if supplier:
                    suppliers.add(supplier)
            if suppliers:
                return f"The following suppliers are mentioned in the data: {', '.join(list(suppliers)[:5])}."

        if "mitigation" in question_lower or "recommend" in question_lower:
            recommendations = self._extract_recommendations(contexts)
            if recommendations:
                return f"Based on the detected risks, here are recommended mitigation actions: {'; '.join(recommendations[:3])}."

        # Default answer
        total = len(contexts)
        if total > 0:
            return f"Found {total} relevant events in the data from {len(sources)} source(s)."
        return "I found limited information in the data. Try asking about specific risk types, suppliers, or mitigation strategies."

    def _extract_recommendations(self, contexts: list) -> list[str]:
        """Extract recommendations from contexts.

        Args:
            contexts: The retrieved contexts

        Returns:
            List of recommendation strings
        """
        recommendations = set()

        for ctx in contexts:
            metadata = ctx.metadata
            if "recommendations" in metadata:
                recs = metadata["recommendations"]
                if isinstance(recs, list):
                    recommendations.update(recs)

        return list(recommendations)[:5]
