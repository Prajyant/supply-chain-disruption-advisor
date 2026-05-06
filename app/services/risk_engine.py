"""
Predictive Risk Engine — cross-reference analysis.

Two-tier system:
  Tier 1 - REACTIVE: Analyzes individual emails for operational signals
            (delays, shortages, quality issues from the sender themselves).
  Tier 2 - PREDICTIVE: Cross-references normal emails + world news to find
            hidden connections and predict future disruptions.

News articles are NEVER analyzed individually — they are context for cross-reference only.
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


# ---------------------------------------------------------------------------
# Keyword maps — used ONLY for individual email reactive analysis
# (NOT for news events)
# ---------------------------------------------------------------------------
EMAIL_SEVERITY_KEYWORDS = {
    "critical": [
        "plant shutdown", "factory fire", "bankruptcy", "insolvency",
        "halt production", "force majeure",
    ],
    "high": [
        "strike", "cyberattack", "quality recall", "production stopped",
        "major delay", "flood", "earthquake",
    ],
    "medium": [
        "shortage", "capacity constraint", "late shipment",
        "backlog", "minor delay", "variance detected",
    ],
}

DISRUPTION_TYPES = {
    "financial": ["bankruptcy", "insolvency"],
    "logistics": ["delay", "late shipment", "strike", "backlog"],
    "geopolitical": ["sanction", "embargo", "export ban"],
    "natural_disaster": ["flood", "earthquake", "hurricane", "typhoon"],
    "operations": ["factory fire", "plant shutdown", "capacity constraint", "shortage", "variance"],
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


class RiskAnalyzer:
    """Predictive risk engine."""

    def __init__(self) -> None:
        pass

    # -----------------------------------------------------------------------
    # Tier 1: Reactive — analyze a SINGLE EMAIL for self-reported problems
    # -----------------------------------------------------------------------

    def analyze_event(self, event: dict[str, Any]) -> RiskAssessment:
        """
        Analyze a single event for risk.

        IMPORTANT: News events are NOT scored here — they are inputs to
        cross-reference, not risk assessments themselves.
        Only operational emails (supplier_email, live_email, inventory) are scored.
        """
        source = str(event.get("source", ""))
        is_news = "news" in source.lower()

        if is_news:
            # Return a neutral placeholder — news is used in cross-reference only
            return self._neutral_news_placeholder(event)

        text = str(event.get("text", ""))

        # Use keyword heuristic
        return self._email_heuristic_assessment(event=event, text=text.lower())

    # -----------------------------------------------------------------------
    # Tier 2: Predictive — cross-reference emails x news
    # -----------------------------------------------------------------------

    def cross_reference(
        self,
        operations: list[dict[str, Any]],
        news_events: list[dict[str, Any]],
    ) -> list[RiskAssessment]:
        """
        Core predictive engine.
        Takes normal operational emails + real-time news, finds
        connections and predicts future disruptions before they happen.
        """
        if not operations or not news_events:
            logger.info("Cross-reference skipped: no operations or no news")
            return []

        return self._heuristic_cross_reference(operations, news_events)

    def answer_question(
        self, question: str, contexts: list[RetrievedContext]
    ) -> tuple[str, list[str]]:
        """Answer a supply chain advisory question."""
        return self._heuristic_chat_answer(question, contexts)

    # -----------------------------------------------------------------------
    # Heuristic cross-reference fallback
    # -----------------------------------------------------------------------

    LOCATION_KEYWORDS: dict[str, list[str]] = {
        "shanghai": ["shanghai", "china", "chinese"],
        "taipei": ["taipei", "taiwan", "taiwanese"],
        "tokyo": ["tokyo", "japan", "japanese"],
        "busan": ["busan", "korea", "korean"],
        "los angeles": ["los angeles", "la port", "long beach", "west coast"],
        "rotterdam": ["rotterdam", "netherlands", "dutch"],
        "guangzhou": ["guangzhou", "guangdong", "south china"],
        "ho chi minh": ["ho chi minh", "vietnam", "vietnamese", "hcmc"],
        "gujarat": ["gujarat", "india", "indian", "mundra"],
        "dubai": ["dubai", "uae", "gulf"],
        "manila": ["manila", "philippines", "philippine"],
        "dhaka": ["dhaka", "bangladesh"],
        "mumbai": ["mumbai", "bombay"],
        "monterrey": ["monterrey", "mexico", "mexican"],
        "chicago": ["chicago", "midwest", "illinois"],
        "london": ["london", "heathrow", "uk", "britain"],
        "perth": ["perth", "australia", "australian"],
        "suez": ["suez", "suez canal"],
        "hormuz": ["hormuz", "persian gulf"],
        "singapore": ["singapore"],
        "mundra": ["mundra", "gujarat", "india", "indian"],
        "suez canal": ["suez canal", "suez"],
    }

    HEURISTIC_NEWS_SEVERITY: dict[str, list[str]] = {
        "critical": ["war", "conflict", "sanctions", "embargo", "export ban", "shutdown", "fire", "bankruptcy", "severe thunderstorm"],
        "high": ["strike", "flood", "earthquake", "typhoon", "hurricane", "cyberattack", "disruption", "congestion", "tariff", "customs delay"],
        "medium": ["delay", "shortage", "tension", "trade restriction", "dispute", "heavy rain", "adverse weather"],
    }

    def _heuristic_cross_reference(
        self,
        operations: list[dict[str, Any]],
        news_events: list[dict[str, Any]],
    ) -> list[RiskAssessment]:
        """Geographic keyword cross-reference."""
        predictions: list[RiskAssessment] = []
        seen: set[str] = set()

        for op_idx, op in enumerate(operations):
            op_text = str(op.get("text", "")).lower()
            op_supplier = (
                op.get("supplier")
                or op.get("metadata", {}).get("sender_name")
                or "Unknown"
            )

            op_locations = {
                loc for loc, kws in self.LOCATION_KEYWORDS.items()
                if any(kw in op_text for kw in kws)
            }
            if not op_locations:
                continue

            for news_idx, news in enumerate(news_events):
                news_text = str(news.get("text", "")).lower()
                news_locations = {
                    loc for loc, kws in self.LOCATION_KEYWORDS.items()
                    if any(kw in news_text for kw in kws)
                }

                overlap = op_locations & news_locations
                if not overlap:
                    continue

                # Determine severity from news content using word boundaries
                severity = "low"
                for sev, terms in self.HEURISTIC_NEWS_SEVERITY.items():
                    if any(re.search(r"\b" + re.escape(t) + r"\b", news_text) for t in terms):
                        severity = sev
                        break

                if severity == "low":
                    continue

                key = f"{op_idx}-{news_idx}"
                if key in seen:
                    continue
                seen.add(key)

                news_headline = self._clean_text(
                    news.get("metadata", {}).get("title", "") or news.get("text", "")[:80]
                )
                location_str = ", ".join(overlap)

                predictions.append(RiskAssessment(
                    risk_id=f"predict-{op_idx}-{news_idx}",
                    source="predictive_analysis",
                    reference_id=f"op{op_idx}-news{news_idx}",
                    detected_at=datetime.now(timezone.utc),
                    disruption_type="geopolitical",
                    severity=severity,
                    confidence={"critical": 0.72, "high": 0.60, "medium": 0.50}.get(severity, 0.40),
                    signals=[f"Email: {op_supplier}", f"Location match: {location_str}"],
                    recommendations=RECOMMENDATION_MAP[severity],
                    summary=(
                        f"Geographic overlap detected at {location_str}. "
                        f"News: \"{news_headline[:100]}\""
                    ),
                    headline=f"\u26a0\ufe0f {op_supplier} — geographic risk overlap",
                    metadata={
                        "type": "prediction",
                        "email_subject": op.get("metadata", {}).get("subject", ""),
                        "email_supplier": op_supplier,
                        "email_origin": location_str,
                        "news_headline": news_headline,
                        "prediction": f"Geographic match: {location_str}",
                        "sender_name": op_supplier,
                    },
                ))

        logger.info(f"Heuristic predicted {len(predictions)} potential disruptions")
        return predictions

    # -----------------------------------------------------------------------
    # Individual email heuristic assessment (Tier 1 reactive)
    # -----------------------------------------------------------------------

    def _email_heuristic_assessment(self, event: dict[str, Any], text: str) -> RiskAssessment:
        """Score a single operational email for self-reported problems."""
        severity = "low"
        for sev, terms in EMAIL_SEVERITY_KEYWORDS.items():
            if any(re.search(r"\b" + re.escape(t) + r"\b", text) for t in terms):
                severity = sev
                break

        disruption_type = "operations"
        for dtype, terms in DISRUPTION_TYPES.items():
            if any(re.search(r"\b" + re.escape(t) + r"\b", text) for t in terms):
                disruption_type = dtype
                break

        # Extract matched signals
        signals: list[str] = []
        for terms in EMAIL_SEVERITY_KEYWORDS.values():
            for t in terms:
                if re.search(r"\b" + re.escape(t) + r"\b", text) and t not in signals:
                    signals.append(t)
        if not signals:
            signals = ["routine operational update"]

        confidence = {"critical": 0.91, "high": 0.79, "medium": 0.66, "low": 0.52}[severity]
        metadata = dict(event.get("metadata", {})) if isinstance(event.get("metadata"), dict) else {}

        supplier = (
            event.get("supplier")
            or metadata.get("sender_name")
            or "Unknown Supplier"
        )
        subject = metadata.get("subject", event.get("text", "")[:60])

        summary = (
            f"Supplier email from {supplier} flagged as {severity.upper()} "
            f"due to: {', '.join(signals[:3])}."
            if severity != "low"
            else f"Routine operational email from {supplier}. No immediate risk signals."
        )

        return RiskAssessment(
            risk_id=f"{event.get('source')}-{event.get('reference_id', '')}",
            source=event.get("source", "unknown"),
            reference_id=str(event.get("reference_id", "")),
            detected_at=datetime.now(timezone.utc),
            disruption_type=disruption_type,
            severity=severity,
            confidence=confidence,
            signals=signals,
            recommendations=RECOMMENDATION_MAP[severity],
            summary=summary,
            headline=subject,
            metadata={**metadata, "sender_name": supplier, "matched_signals": signals},
        )

    def _neutral_news_placeholder(self, event: dict[str, Any]) -> RiskAssessment:
        """Placeholder for news events — they are context only, not individual risks."""
        metadata = dict(event.get("metadata", {})) if isinstance(event.get("metadata"), dict) else {}
        title = self._clean_text(metadata.get("title", "") or event.get("text", "")[:80])
        return RiskAssessment(
            risk_id=f"news-{event.get('reference_id', '')}",
            source=event.get("source", "news_feed"),
            reference_id=str(event.get("reference_id", "")),
            detected_at=datetime.now(timezone.utc),
            disruption_type="operations",
            severity="low",
            confidence=0.0,
            signals=[],
            recommendations=[],
            summary=title,
            headline=title,
            metadata={**metadata, "_news_context_only": True},
        )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _build_operations_summary(self, operations: list[dict[str, Any]]) -> str:
        lines = []
        for i, op in enumerate(operations):
            supplier = (
                op.get("supplier")
                or op.get("metadata", {}).get("sender_name")
                or "Unknown"
            )
            meta = op.get("metadata", {}) or {}
            subject = meta.get("subject", "")
            origin = meta.get("origin_location", "")
            eta = meta.get("eta_days", "")
            material = meta.get("material", "")
            body = str(op.get("text", ""))[:250]
            lines.append(
                f"[{i}] Supplier: {supplier} | Subject: {subject} | "
                f"Origin: {origin} | ETA: {eta} days | Material: {material} | "
                f"Body excerpt: {body}"
            )
        return "\n".join(lines)

    def _build_news_summary(self, news_events: list[dict[str, Any]]) -> str:
        lines = []
        for i, news in enumerate(news_events[:40]):  # cap at 40
            headline = self._clean_text(
                news.get("metadata", {}).get("title", "")
                or news.get("text", "")[:120]
            )
            source = news.get("source", "")
            lines.append(f"[{i}] ({source}) {headline}")
        return "\n".join(lines)

    def _clean_text(self, value: Any) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", str(value or ""))
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _heuristic_chat_answer(
        self, question: str, contexts: list[RetrievedContext]
    ) -> tuple[str, list[str]]:
        recs = RECOMMENDATION_MAP["medium"]
        answer = (
            "Based on retrieved context, supply chain risk exposure is moderate. "
            "Primary risks include potential delays in material availability."
        )
        return answer, recs
