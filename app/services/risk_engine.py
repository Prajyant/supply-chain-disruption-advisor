from __future__ import annotations
from datetime import datetime, timezone
import json
import re
from typing import Any
from app.core.config import get_settings
from app.models.schemas import RetrievedContext, RiskAssessment

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


SEVERITY_KEYWORDS = {
    "critical": [
        "bankruptcy",
        "factory fire",
        "plant shutdown",
        "embargo",
        "sanction",
        "war",
        "insolvency",
    ],
    "high": [
        "port congestion",
        "strike",
        "export ban",
        "flood",
        "earthquake",
        "cyberattack",
        "quality recall",
        "delay",
    ],
    "medium": [
        "price increase",
        "capacity constraint",
        "shortage",
        "late shipment",
        "backlog",
        "weather alert",
    ],
}

DISRUPTION_TYPES = {
    "financial": ["bankruptcy", "insolvency"],
    "logistics": ["delay", "port congestion", "late shipment", "strike"],
    "geopolitical": ["war", "sanction", "embargo", "export ban"],
    "natural_disaster": ["flood", "earthquake", "weather alert", "hurricane"],
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


class RiskAnalyzer:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_model
        self._client = OpenAI(api_key=settings.openai_api_key) if (OpenAI and settings.openai_api_key) else None

    def analyze_event(self, event: dict[str, Any]) -> RiskAssessment:
        text = str(event.get("text", ""))
        if self._client is None:
            return self._heuristic_assessment(event=event, text=text)
        llm_result = self._try_llm(event=event, text=text)
        return llm_result if llm_result else self._heuristic_assessment(event=event, text=text)

    def answer_question(self, question: str, contexts: list[RetrievedContext]) -> tuple[str, list[str]]:
        joined = "\n".join([f"- [{c.source}] {c.text}" for c in contexts[:6]])
        if self._client:
            try:
                prompt = (
                    "You are a supply chain disruption advisor.\n"
                    "Use the provided context to answer clearly and suggest practical mitigation actions.\n"
                    f"Question: {question}\n\nContext:\n{joined}\n"
                    "Return plain text with a concise answer and bullet recommendations."
                )
                response = self._client.responses.create(
                    model=self.model,
                    input=prompt,
                    temperature=0.2,
                )
                text = response.output_text.strip()
                recs = [line.lstrip("- ").strip() for line in text.splitlines() if line.strip().startswith("-")]
                return text, recs[:5]
            except Exception:
                pass
        return self._heuristic_chat_answer(question, contexts)

    def _heuristic_chat_answer(self, question: str, contexts: list[RetrievedContext]) -> tuple[str, list[str]]:
        compiled_text = " ".join(c.text.lower() for c in contexts)
        severity = self._infer_severity(compiled_text)
        recs = RECOMMENDATION_MAP[severity]
        answer = (
            f"Likely disruption exposure is **{severity.upper()}** based on retrieved context. "
            "Primary risks indicate potential delays in material availability and production continuity."
        )
        if "alternate supplier" in question.lower() or "alternative supplier" in question.lower():
            answer += " Prioritize onboarding backup suppliers in the same commodity category."
        return answer, recs

    def _try_llm(self, event: dict[str, Any], text: str) -> RiskAssessment | None:
        try:
            prompt = (
                "Classify supply-chain disruption risk from the event text.\n"
                "Return strict JSON with keys: disruption_type, severity, confidence, signals, summary, recommendations.\n"
                f"Event source: {event.get('source')}\n"
                f"Event text: {text}\n"
            )
            response = self._client.responses.create(
                model=self.model,
                input=prompt,
                temperature=0.1,
            )
            raw = response.output_text.strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return None
            payload = json.loads(match.group(0))
            severity = str(payload.get("severity", "medium")).lower()
            if severity not in {"low", "medium", "high", "critical"}:
                severity = "medium"
            disruption_type = str(payload.get("disruption_type", "unknown"))
            signals = [str(s) for s in payload.get("signals", [])][:8]
            metadata = dict(event.get("metadata", {})) if isinstance(event.get("metadata", {}), dict) else {}
            headline = ""
            summary = self._clean_text(str(payload.get("summary", "")))

            if self._is_news_event(event):
                headline, article_excerpt = self._extract_news_content(event=event, text=text)
                if article_excerpt:
                    metadata.setdefault("article_excerpt", article_excerpt)
                metadata.setdefault("title", headline)
                summary = article_excerpt if article_excerpt else summary

            risk_reason = self._build_risk_reason(
                severity=severity,
                disruption_type=disruption_type,
                signals=signals,
            )
            metadata["risk_reason"] = risk_reason
            metadata["matched_signals"] = signals
            return RiskAssessment(
                risk_id=f"{event.get('source')}-{event.get('reference_id')}",
                source=event.get("source", "unknown"),
                reference_id=str(event.get("reference_id", "")),
                detected_at=datetime.now(timezone.utc),
                disruption_type=disruption_type,
                severity=severity,
                confidence=float(payload.get("confidence", 0.65)),
                signals=signals,
                recommendations=[str(r) for r in payload.get("recommendations", RECOMMENDATION_MAP[severity])][:6],
                summary=summary,
                headline=headline,
                metadata=metadata,
            )
        except Exception:
            return None

    def _heuristic_assessment(self, event: dict[str, Any], text: str) -> RiskAssessment:
        low_text = text.lower()
        severity = self._infer_severity(low_text)
        disruption_type = self._infer_disruption_type(low_text)
        signals = self._extract_signals(low_text)
        metadata = dict(event.get("metadata", {})) if isinstance(event.get("metadata", {}), dict) else {}
        confidence = {
            "critical": 0.93,
            "high": 0.83,
            "medium": 0.72,
            "low": 0.58,
        }[severity]
        raw_text = str(event.get("text", ""))
        headline = ""
        risk_reason = self._build_risk_reason(
            severity=severity,
            disruption_type=disruption_type,
            signals=signals,
        )

        if self._is_news_event(event):
            headline, article_excerpt = self._extract_news_content(event=event, text=raw_text)
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

    def _is_news_event(self, event: dict[str, Any]) -> bool:
        return "news" in str(event.get("source", "")).lower()

    def _clean_text(self, value: Any) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", str(value or ""))
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _extract_news_content(self, event: dict[str, Any], text: str) -> tuple[str, str]:
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata", {}), dict) else {}
        headline = self._clean_text(metadata.get("title") or metadata.get("headline") or "")
        article_excerpt = self._clean_text(metadata.get("summary") or metadata.get("content") or "")

        if not headline:
            first_sentence = text.split(". ", 1)[0] if ". " in text else text
            headline = self._clean_text(first_sentence)

        if not article_excerpt:
            if ". " in text:
                parts = text.split(". ", 1)
                article_excerpt = self._clean_text(parts[1]) if len(parts) > 1 and parts[1].strip() else self._clean_text(text)
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

    def _infer_severity(self, text: str) -> str:
        for severity, terms in SEVERITY_KEYWORDS.items():
            if any(term in text for term in terms):
                return severity
        return "low"

    def _infer_disruption_type(self, text: str) -> str:
        for disruption_type, terms in DISRUPTION_TYPES.items():
            if any(term in text for term in terms):
                return disruption_type
        return "operations"

    def _extract_signals(self, text: str) -> list[str]:
        found: list[str] = []
        for terms in SEVERITY_KEYWORDS.values():
            for term in terms:
                if term in text and term not in found:
                    found.append(term)
        return found[:6] if found else ["monitoring signal"]
