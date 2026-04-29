"""
Predictive Risk Engine — Gemini-powered cross-reference analysis.

This engine does NOT just scan individual emails for disaster keywords.
Instead, it:
1. Extracts operational state from normal emails (supplier, location, ETA)
2. Reads real-time world news headlines
3. Uses Gemini to cross-reference them and PREDICT disruptions
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.models.schemas import RetrievedContext, RiskAssessment

logger = logging.getLogger(__name__)

try:
    from google import genai
except Exception:
    genai = None


# ---------------------------------------------------------------------------
# Heuristic fallback maps (used when Gemini is unavailable)
# ---------------------------------------------------------------------------
SEVERITY_KEYWORDS = {
    "critical": [
        "bankruptcy", "factory fire", "plant shutdown", "embargo",
        "sanction", "war", "insolvency",
    ],
    "high": [
        "port congestion", "strike", "export ban", "flood",
        "earthquake", "cyberattack", "quality recall", "delay",
    ],
    "medium": [
        "price increase", "capacity constraint", "shortage",
        "late shipment", "backlog", "weather alert",
    ],
}

DISRUPTION_TYPES = {
    "financial": ["bankruptcy", "insolvency"],
    "logistics": ["delay", "port congestion", "late shipment", "strike"],
    "geopolitical": ["war", "sanction", "embargo", "export ban"],
    "natural_disaster": ["flood", "earthquake", "weather alert", "hurricane", "typhoon"],
    "operations": ["factory fire", "plant shutdown", "capacity constraint", "shortage"],
    "quality": ["quality recall"],
    "security": ["cyberattack"],
}

RECOMMENDATION_MAP = {
    "critical": [
        "Immediately qualify alternate suppliers for impacted SKUs.",
        "Trigger emergency buffer stock release for affected production lines.",
        "Escalate to executive S&OP war-room for daily risk monitoring.",
    ],
    "high": [
        "Reschedule non-critical production to preserve constrained materials.",
        "Increase safety stock targets for the next 2 planning cycles.",
        "Prioritize inbound logistics capacity on high-margin orders.",
    ],
    "medium": [
        "Review purchase order split across primary and secondary suppliers.",
        "Increase monitoring cadence for supplier OTIF and lead times.",
        "Prepare contingent transport mode shift if delays worsen.",
    ],
    "low": [
        "Continue monitoring and keep current replenishment policy.",
        "Log signal in weekly supplier risk review.",
    ],
}


# ---------------------------------------------------------------------------
# Location keyword map for heuristic geographic matching
# ---------------------------------------------------------------------------
LOCATION_KEYWORDS = {
    "shanghai": ["shanghai", "china", "chinese"],
    "taipei": ["taipei", "taiwan", "taiwanese"],
    "tokyo": ["tokyo", "japan", "japanese"],
    "busan": ["busan", "korea", "korean"],
    "los angeles": ["los angeles", "la port", "long beach", "california", "west coast"],
    "rotterdam": ["rotterdam", "netherlands", "dutch", "europe"],
    "newark": ["newark", "new jersey", "east coast"],
    "guangzhou": ["guangzhou", "guangdong", "south china"],
    "ho chi minh": ["ho chi minh", "vietnam", "vietnamese", "hcmc"],
    "gujarat": ["gujarat", "india", "indian", "mundra"],
    "suez": ["suez", "suez canal"],
    "hormuz": ["hormuz", "strait of hormuz", "persian gulf"],
    "panama": ["panama", "panama canal"],
    "singapore": ["singapore", "malacca"],
}


class RiskAnalyzer:
    """Predictive risk engine that cross-references emails with news."""

    def __init__(self) -> None:
        settings = get_settings()
        self._gemini_client = None
        self._gemini_model = settings.gemini_model

        if genai and settings.gemini_api_key:
            try:
                self._gemini_client = genai.Client(api_key=settings.gemini_api_key)
                logger.info("Gemini client initialized for predictive analysis")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def analyze_event(self, event: dict[str, Any]) -> RiskAssessment:
        """Analyze a single event (email or news) for risk signals."""
        text = str(event.get("text", ""))
        return self._heuristic_assessment(event=event, text=text)

    def cross_reference(
        self,
        operations: list[dict[str, Any]],
        news_events: list[dict[str, Any]],
    ) -> list[RiskAssessment]:
        """
        The core predictive engine.

        Takes normal operational emails and real-time news, then uses Gemini
        to predict which operations might be impacted by current world events.
        """
        if not operations or not news_events:
            return []

        if self._gemini_client:
            return self._gemini_cross_reference(operations, news_events)
        else:
            return self._heuristic_cross_reference(operations, news_events)

    def answer_question(
        self, question: str, contexts: list[RetrievedContext]
    ) -> tuple[str, list[str]]:
        """Answer a supply chain advisory question."""
        joined = "\n".join([f"- [{c.source}] {c.text}" for c in contexts[:6]])
        if self._gemini_client:
            try:
                prompt = (
                    "You are a supply chain disruption advisor.\n"
                    "Use the provided context to answer clearly and suggest practical mitigation actions.\n"
                    f"Question: {question}\n\nContext:\n{joined}\n"
                    "Return plain text with a concise answer and bullet recommendations."
                )
                response = self._gemini_client.models.generate_content(
                    model=self._gemini_model,
                    contents=prompt,
                )
                text = response.text.strip()
                recs = [
                    line.lstrip("- ").strip()
                    for line in text.splitlines()
                    if line.strip().startswith("-")
                ]
                return text, recs[:5]
            except Exception as e:
                logger.warning(f"Gemini chat failed: {e}")
        return self._heuristic_chat_answer(question, contexts)

    # -----------------------------------------------------------------------
    # Gemini-powered cross-reference (the magic)
    # -----------------------------------------------------------------------

    def _gemini_cross_reference(
        self,
        operations: list[dict[str, Any]],
        news_events: list[dict[str, Any]],
    ) -> list[RiskAssessment]:
        """Use Gemini to cross-reference operations with news."""
        predictions: list[RiskAssessment] = []

        # Build a compact summary of all active operations
        ops_summary = self._build_operations_summary(operations)

        # Build a compact summary of all news headlines
        news_summary = self._build_news_summary(news_events)

        prompt = f"""You are an expert supply chain risk analyst. Your job is to PREDICT disruptions by cross-referencing normal operational data with current world news.

## Active Supply Chain Operations
{ops_summary}

## Current World News
{news_summary}

## Your Task
Analyze the news headlines and identify which of the active operations above could be affected. For each potential impact, return a JSON object.

IMPORTANT: Only flag genuine geographic or thematic connections. If a news article about a flood in India has no connection to any operation, skip it.

Return a JSON array of predictions. Each prediction must have:
- "operation_index": (int) index of the affected operation (0-based)
- "news_index": (int) index of the news article causing the risk (0-based)
- "severity": "critical" | "high" | "medium" | "low"
- "disruption_type": "logistics" | "geopolitical" | "natural_disaster" | "financial" | "operations" | "security"
- "confidence": (float 0.0-1.0)
- "prediction": (string) A clear 1-2 sentence explanation of WHY this news affects this operation
- "recommendations": (array of 2-3 actionable strings)

If no connections exist, return an empty array: []

Return ONLY the JSON array, no other text."""

        try:
            response = self._gemini_client.models.generate_content(
                model=self._gemini_model,
                contents=prompt,
            )
            raw = response.text.strip()

            # Extract JSON array
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                logger.warning("Gemini returned no valid JSON array")
                return self._heuristic_cross_reference(operations, news_events)

            results = json.loads(match.group(0))

            for pred in results:
                op_idx = int(pred.get("operation_index", -1))
                news_idx = int(pred.get("news_index", -1))

                if op_idx < 0 or op_idx >= len(operations):
                    continue
                if news_idx < 0 or news_idx >= len(news_events):
                    continue

                op = operations[op_idx]
                news = news_events[news_idx]
                severity = str(pred.get("severity", "medium")).lower()
                if severity not in {"low", "medium", "high", "critical"}:
                    severity = "medium"

                # Build the headline showing the connection
                op_supplier = op.get("supplier", op.get("metadata", {}).get("sender_name", "Unknown"))
                news_headline = self._clean_text(
                    news.get("metadata", {}).get("title", "")
                    or news.get("text", "")[:80]
                )

                headline = f"⚠️ {op_supplier} shipment may be impacted"
                prediction_text = str(pred.get("prediction", ""))
                recommendations = [str(r) for r in pred.get("recommendations", RECOMMENDATION_MAP[severity])]

                predictions.append(RiskAssessment(
                    risk_id=f"predict-{op_idx}-{news_idx}",
                    source="predictive_analysis",
                    reference_id=f"op{op_idx}-news{news_idx}",
                    detected_at=datetime.now(timezone.utc),
                    disruption_type=str(pred.get("disruption_type", "logistics")),
                    severity=severity,
                    confidence=float(pred.get("confidence", 0.7)),
                    signals=[f"Email: {op_supplier}", f"News: {news_headline[:60]}"],
                    recommendations=recommendations[:3],
                    summary=prediction_text,
                    headline=headline,
                    metadata={
                        "type": "prediction",
                        "email_subject": op.get("metadata", {}).get("subject", op.get("text", "")[:60]),
                        "email_supplier": op_supplier,
                        "email_origin": op.get("metadata", {}).get("origin_location", ""),
                        "news_headline": news_headline,
                        "news_source": news.get("source", ""),
                        "prediction": prediction_text,
                        "sender_name": op_supplier,
                    },
                ))

            logger.info(f"Gemini predicted {len(predictions)} potential disruptions")
            return predictions

        except Exception as e:
            logger.error(f"Gemini cross-reference failed: {e}")
            return self._heuristic_cross_reference(operations, news_events)

    # -----------------------------------------------------------------------
    # Heuristic cross-reference (fallback when Gemini is unavailable)
    # -----------------------------------------------------------------------

    def _heuristic_cross_reference(
        self,
        operations: list[dict[str, Any]],
        news_events: list[dict[str, Any]],
    ) -> list[RiskAssessment]:
        """Geographic keyword matching fallback."""
        predictions: list[RiskAssessment] = []

        for op_idx, op in enumerate(operations):
            op_text = str(op.get("text", "")).lower()
            op_supplier = op.get("supplier", op.get("metadata", {}).get("sender_name", "Unknown"))

            # Find which locations this operation touches
            op_locations = set()
            for loc_key, keywords in LOCATION_KEYWORDS.items():
                if any(kw in op_text for kw in keywords):
                    op_locations.add(loc_key)

            if not op_locations:
                continue

            # Check each news event for geographic overlap
            for news_idx, news in enumerate(news_events):
                news_text = str(news.get("text", "")).lower()
                news_headline = self._clean_text(
                    news.get("metadata", {}).get("title", "")
                    or news.get("text", "")[:80]
                )

                # Find locations mentioned in the news
                news_locations = set()
                for loc_key, keywords in LOCATION_KEYWORDS.items():
                    if any(kw in news_text for kw in keywords):
                        news_locations.add(loc_key)

                # Check for overlap
                overlap = op_locations & news_locations
                if not overlap:
                    continue

                # Determine severity from the news content
                severity = self._infer_severity(news_text)
                if severity == "low":
                    continue  # Skip low-severity news matches

                disruption_type = self._infer_disruption_type(news_text)
                location_str = ", ".join(overlap)

                predictions.append(RiskAssessment(
                    risk_id=f"predict-{op_idx}-{news_idx}",
                    source="predictive_analysis",
                    reference_id=f"op{op_idx}-news{news_idx}",
                    detected_at=datetime.now(timezone.utc),
                    disruption_type=disruption_type,
                    severity=severity,
                    confidence={"critical": 0.85, "high": 0.75, "medium": 0.65}.get(severity, 0.5),
                    signals=[f"Email: {op_supplier}", f"News: {news_headline[:60]}", f"Location: {location_str}"],
                    recommendations=RECOMMENDATION_MAP[severity],
                    summary=(
                        f"News about {disruption_type.replace('_', ' ')} near {location_str} "
                        f"may affect {op_supplier}'s operations. "
                        f"News: \"{news_headline[:100]}\""
                    ),
                    headline=f"⚠️ {op_supplier} shipment may be impacted",
                    metadata={
                        "type": "prediction",
                        "email_subject": op.get("metadata", {}).get("subject", ""),
                        "email_supplier": op_supplier,
                        "email_origin": location_str,
                        "news_headline": news_headline,
                        "news_source": news.get("source", ""),
                        "prediction": f"Geographic match: {location_str}",
                        "sender_name": op_supplier,
                    },
                ))

        logger.info(f"Heuristic predicted {len(predictions)} potential disruptions")
        return predictions

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_operations_summary(self, operations: list[dict[str, Any]]) -> str:
        """Build a concise text summary of active operations for the LLM prompt."""
        lines = []
        for i, op in enumerate(operations):
            supplier = op.get("supplier", op.get("metadata", {}).get("sender_name", "Unknown"))
            text = str(op.get("text", ""))[:200]
            meta = op.get("metadata", {})
            origin = meta.get("origin_location", "")
            eta = meta.get("eta_days", "")
            material = meta.get("material", "")
            lines.append(
                f"[{i}] Supplier: {supplier} | Origin: {origin} | ETA: {eta} days | "
                f"Material: {material} | Details: {text}"
            )
        return "\n".join(lines)

    def _build_news_summary(self, news_events: list[dict[str, Any]]) -> str:
        """Build a concise text summary of news for the LLM prompt."""
        lines = []
        for i, news in enumerate(news_events):
            headline = self._clean_text(
                news.get("metadata", {}).get("title", "")
                or news.get("text", "")[:120]
            )
            source = news.get("source", "unknown")
            lines.append(f"[{i}] ({source}) {headline}")
        return "\n".join(lines[:30])  # cap at 30 headlines

    def _heuristic_assessment(self, event: dict[str, Any], text: str) -> RiskAssessment:
        """Keyword-based assessment for individual events."""
        low_text = text.lower()
        severity = self._infer_severity(low_text)
        disruption_type = self._infer_disruption_type(low_text)
        signals = self._extract_signals(low_text)
        metadata = dict(event.get("metadata", {})) if isinstance(event.get("metadata"), dict) else {}
        confidence = {"critical": 0.93, "high": 0.83, "medium": 0.72, "low": 0.58}[severity]

        headline = ""
        risk_reason = self._build_risk_reason(severity, disruption_type, signals)

        if self._is_news_event(event):
            headline, article_excerpt = self._extract_news_content(event=event, text=text)
            summary = article_excerpt if article_excerpt else risk_reason
            metadata.setdefault("article_excerpt", article_excerpt)
            metadata.setdefault("title", headline)
        else:
            summary = risk_reason

        metadata["risk_reason"] = risk_reason
        metadata["matched_signals"] = signals

        return RiskAssessment(
            risk_id=f"{event.get('source')}-{event.get('reference_id')}",
            source=event.get("source", "unknown"),
            reference_id=str(event.get("reference_id", "")),
            detected_at=datetime.now(timezone.utc),
            disruption_type=disruption_type,
            severity=severity,
            confidence=confidence,
            signals=signals,
            recommendations=RECOMMENDATION_MAP[severity],
            summary=summary,
            headline=headline,
            metadata=metadata,
        )

    def _heuristic_chat_answer(
        self, question: str, contexts: list[RetrievedContext]
    ) -> tuple[str, list[str]]:
        compiled_text = " ".join(c.text.lower() for c in contexts)
        severity = self._infer_severity(compiled_text)
        recs = RECOMMENDATION_MAP[severity]
        answer = (
            f"Likely disruption exposure is **{severity.upper()}** based on retrieved context. "
            "Primary risks indicate potential delays in material availability and production continuity."
        )
        return answer, recs

    def _is_news_event(self, event: dict[str, Any]) -> bool:
        return "news" in str(event.get("source", "")).lower()

    def _clean_text(self, value: Any) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", str(value or ""))
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _extract_news_content(self, event: dict[str, Any], text: str) -> tuple[str, str]:
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        headline = self._clean_text(metadata.get("title") or metadata.get("headline") or "")
        article_excerpt = self._clean_text(metadata.get("summary") or metadata.get("content") or "")

        if not headline:
            first_sentence = text.split(". ", 1)[0] if ". " in text else text
            headline = self._clean_text(first_sentence)

        if not article_excerpt:
            if ". " in text:
                parts = text.split(". ", 1)
                article_excerpt = self._clean_text(parts[1]) if len(parts) > 1 else self._clean_text(text)
            else:
                article_excerpt = self._clean_text(text)

        return headline[:180], article_excerpt[:450]

    def _build_risk_reason(self, severity: str, disruption_type: str, signals: list[str]) -> str:
        normalized_type = disruption_type.replace("_", " ")
        signal_text = ", ".join(signals[:4]) if signals else "contextual disruption indicators"
        return (
            f"Classified as {severity.upper()} {normalized_type} risk due to detected signals: "
            f"{signal_text}."
        )

    def _match_keyword(self, term: str, text: str) -> bool:
        """Check if a keyword appears as a whole word (not inside another word)."""
        return bool(re.search(r'\b' + re.escape(term) + r'\b', text))

    def _infer_severity(self, text: str) -> str:
        for severity, terms in SEVERITY_KEYWORDS.items():
            if any(self._match_keyword(term, text) for term in terms):
                return severity
        return "low"

    def _infer_disruption_type(self, text: str) -> str:
        for disruption_type, terms in DISRUPTION_TYPES.items():
            if any(self._match_keyword(term, text) for term in terms):
                return disruption_type
        return "operations"

    def _extract_signals(self, text: str) -> list[str]:
        found: list[str] = []
        for terms in SEVERITY_KEYWORDS.values():
            for term in terms:
                if self._match_keyword(term, text) and term not in found:
                    found.append(term)
        return found[:6] if found else ["monitoring signal"]
