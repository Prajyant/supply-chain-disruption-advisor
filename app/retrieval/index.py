from __future__ import annotations
from typing import Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.models.schemas import RetrievedContext


class RetrievalIndex:
    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
        self._matrix = None
        self._chunks: list[dict[str, Any]] = []

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def build(self, events: list[dict[str, Any]], chunk_size: int = 350) -> None:
        chunks: list[dict[str, Any]] = []
        for event in events:
            text = str(event.get("text", ""))
            parts = self._chunk_text(text=text, chunk_size=chunk_size)
            for idx, part in enumerate(parts):
                chunks.append(
                    {
                        "source": event["source"],
                        "reference_id": event["reference_id"],
                        "text": part,
                        "metadata": {
                            **event.get("metadata", {}),
                            "chunk_index": idx,
                            "supplier": event.get("supplier", ""),
                        },
                    }
                )
        self._chunks = chunks
        corpus = [c["text"] for c in self._chunks]
        self._matrix = self._vectorizer.fit_transform(corpus) if corpus else None

    def query(self, question: str, top_k: int = 5) -> list[RetrievedContext]:
        if not question.strip() or self._matrix is None or not self._chunks:
            return []
        q_vec = self._vectorizer.transform([question])
        sims = cosine_similarity(q_vec, self._matrix).flatten()
        ranked_idx = sims.argsort()[::-1][:top_k]
        contexts: list[RetrievedContext] = []
        for idx in ranked_idx:
            chunk = self._chunks[int(idx)]
            contexts.append(
                RetrievedContext(
                    source=chunk["source"],
                    reference_id=chunk["reference_id"],
                    text=chunk["text"],
                    score=float(sims[int(idx)]),
                    metadata=chunk["metadata"],
                )
            )
        return contexts

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 350) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        chunks: list[str] = []
        for i in range(0, len(words), chunk_size):
            chunks.append(" ".join(words[i : i + chunk_size]))
        return chunks
