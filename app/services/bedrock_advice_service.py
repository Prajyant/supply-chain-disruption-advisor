"""Amazon Bedrock reasoning and guardrails for shipment risk decisions."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.models.schemas import ShipmentInput, ShipmentRiskAdviceResponse

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None
    ClientError = None
    NoCredentialsError = None


# ==================== PRODUCTION LINE MAPPING ====================
PRODUCTION_LINE_MAP: dict[str, list[str]] = {
    "electronics": ["Assembly Line A", "PCB Manufacturing", "Final QC Line"],
    "pcb": ["Assembly Line A", "PCB Manufacturing", "Final QC Line"],
    "semiconductor": ["Assembly Line A", "PCB Manufacturing", "Final QC Line"],
    "chip": ["Assembly Line A", "PCB Manufacturing", "Final QC Line"],
    "capacitor": ["Assembly Line A", "PCB Manufacturing", "Final QC Line"],
    "resistor": ["Assembly Line A", "PCB Manufacturing", "Final QC Line"],
    "chemical": ["Chemical Processing Unit", "Injection Molding Line"],
    "polymer": ["Chemical Processing Unit", "Injection Molding Line"],
    "resin": ["Chemical Processing Unit", "Injection Molding Line"],
    "adhesive": ["Chemical Processing Unit", "Injection Molding Line"],
    "solvent": ["Chemical Processing Unit", "Injection Molding Line"],
    "metal": ["Stamping Line B", "Welding Assembly"],
    "steel": ["Stamping Line B", "Welding Assembly"],
    "aluminum": ["Stamping Line B", "Welding Assembly"],
    "copper": ["Stamping Line B", "Welding Assembly"],
    "iron": ["Stamping Line B", "Welding Assembly"],
    "titanium": ["Stamping Line B", "Welding Assembly"],
}

DEFAULT_PRODUCTION_LINES = ["Production Line Alpha", "Production Line Beta"]


def calculate_financial_impact(
    shipment: ShipmentInput,
    score_result: dict[str, Any],
) -> dict[str, Any]:
    """Compute financial impact metrics from real shipment data and risk scores."""
    declared_value = float(shipment.declared_value_usd or 0.0)
    risk_score = float(score_result.get("risk_score", 0.0))
    risk_level = str(score_result.get("risk_level", "low")).lower()
    lead_time_days = float(shipment.lead_time_days) if shipment.lead_time_days else 1.0
    transport_mode = (shipment.transport_mode or "").lower().strip()
    material = (shipment.material or "").lower().strip()

    base_exposure = declared_value * 2.5
    raw_exposure = base_exposure * (risk_score / 10.0)
    financial_exposure_usd = max(50_000.0, min(raw_exposure, 10_000_000.0))

    lead_time_safe = max(lead_time_days, 1.0)
    daily_cost_usd = financial_exposure_usd / lead_time_safe

    if transport_mode == "sea" and risk_level in ("high", "critical"):
        mitigation_cost_usd = declared_value * 0.08
    elif risk_level == "medium":
        mitigation_cost_usd = declared_value * 0.03
    else:
        mitigation_cost_usd = declared_value * 0.01

    net_saving_if_act_now_usd = financial_exposure_usd - mitigation_cost_usd

    production_lines: list[str] = DEFAULT_PRODUCTION_LINES
    for keyword, lines in PRODUCTION_LINE_MAP.items():
        if keyword in material:
            production_lines = lines
            break

    halt_date_estimate: str | None = None
    eta_str = shipment.eta_date
    if eta_str:
        try:
            eta_date = datetime.strptime(eta_str, "%Y-%m-%d")
            if risk_level == "critical":
                halt_date_estimate = (eta_date - timedelta(days=3)).strftime("%Y-%m-%d")
            elif risk_level == "high":
                halt_date_estimate = eta_date.strftime("%Y-%m-%d")
            elif risk_level == "medium":
                halt_date_estimate = (eta_date + timedelta(days=5)).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    return {
        "financial_exposure_usd": round(financial_exposure_usd, 2),
        "daily_cost_usd": round(daily_cost_usd, 2),
        "mitigation_cost_usd": round(mitigation_cost_usd, 2),
        "net_saving_if_act_now_usd": round(net_saving_if_act_now_usd, 2),
        "production_lines_at_risk": production_lines,
        "halt_date_estimate": halt_date_estimate,
    }


class BedrockAdviceService:
    """Convert quantitative shipment scores into validated advice JSON using Amazon Bedrock."""

    def __init__(self) -> None:
        self._client = None
        self._model_id = None
        self._last_error = None
        self._init_client()

    def _init_client(self) -> None:
        settings = get_settings()
        self._model_id = settings.bedrock_model_id

        # Prefer Groq when configured; fall back to Bedrock otherwise.
        if settings.groq_api_key:
            try:
                from app.services.groq_client import GroqConverseClient

                groq_client = GroqConverseClient()
                if groq_client.available:
                    self._client = groq_client
                    self._model_id = settings.groq_model
                    self._last_error = None
                    logger.info("Advice LLM backend: Groq (model=%s)", self._model_id)
                    return
            except Exception as exc:
                logger.warning("Groq advice initialization failed, falling back to Bedrock: %s", exc)

        if not boto3:
            self._last_error = "boto3_not_installed"
            return

        try:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id or None,
                aws_secret_access_key=settings.aws_secret_access_key or None,
                aws_session_token=settings.aws_session_token or None,
            )
            self._last_error = None
            logger.info("Bedrock advice client initialized: model=%s, region=%s", self._model_id, settings.aws_region)
        except Exception as exc:
            logger.warning("Bedrock advice initialization failed: %s", exc)
            self._last_error = classify_bedrock_error(exc)
            self._client = None

    def build_advice(
        self,
        *,
        shipment: ShipmentInput,
        score_result: dict[str, Any],
        question: str | None = None,
    ) -> ShipmentRiskAdviceResponse:
        """Return validated shipment advice using Bedrock with a deterministic fallback."""
        if self._client is None:
            self._init_client()

        if self._client:
            advice = self._bedrock_advice(shipment=shipment, score_result=score_result, question=question)
            if advice:
                return advice

        return self._fallback_advice(shipment=shipment, score_result=score_result)

    def _bedrock_advice(
        self,
        *,
        shipment: ShipmentInput,
        score_result: dict[str, Any],
        question: str | None,
    ) -> ShipmentRiskAdviceResponse | None:
        self._last_error = None
        shipment_data = compact_shipment_for_prompt(shipment)
        score_data = compact_score_result_for_prompt(score_result)
        prompt = build_advice_prompt(shipment_data, score_data, question)

        try:
            response = self._client.converse(
                modelId=self._model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.1,
                },
            )
            response_text = extract_response_text(response)
            payload = extract_json_object(response_text)
            guarded = apply_guardrails(payload, score_result)
            financial = calculate_financial_impact(shipment, score_result)
            guarded.update(financial)
            return ShipmentRiskAdviceResponse(**guarded)
        except json.JSONDecodeError as exc:
            logger.warning("Bedrock advice returned invalid JSON: %s", exc)
            self._last_error = "bedrock_response_invalid_json"
        except ValidationError as exc:
            logger.warning("Bedrock advice failed validation: %s", exc)
            self._last_error = "bedrock_response_validation_failed"
        except ValueError as exc:
            logger.warning("Bedrock advice returned no usable text: %s", exc)
            self._last_error = "bedrock_response_empty_or_truncated"
        except Exception as exc:
            logger.warning("Bedrock advice call failed: %s", exc)
            self._last_error = classify_bedrock_error(exc)

        return None

    def _fallback_advice(
        self,
        *,
        shipment: ShipmentInput,
        score_result: dict[str, Any],
    ) -> ShipmentRiskAdviceResponse:
        score = float(score_result["risk_score"])
        level = score_result["risk_level"]
        signals = list(score_result.get("signals", []))
        actions = fallback_actions(level, shipment=shipment, score_result=score_result)

        reason = fallback_reason(shipment=shipment, score_result=score_result, level=level, score=score, signals=signals)
        reasoning_method = "deterministic_guardrail_fallback"
        if self._last_error:
            reasoning_method = f"{reasoning_method}_{self._last_error}"

        financial = calculate_financial_impact(shipment, score_result)

        return ShipmentRiskAdviceResponse(
            shipment_id=shipment.shipment_id,
            risk_score=score,
            risk_level=level,
            decision=decision_for_level(level),
            reason=reason,
            recommended_actions=actions,
            confidence_score=fallback_confidence(level, score_result),
            escalation_required=level in {"high", "critical"},
            scoring_method=score_result["scoring_method"],
            reasoning_method=reasoning_method,
            model_version=score_result["model_version"],
            signals=signals,
            features=score_result["features"],
            evidence_events=list(score_result.get("evidence_events", [])),
            context_events=list(score_result.get("context_events", [])),
            event_explanations=fallback_event_explanations(shipment=shipment, score_result=score_result),
            financial_exposure_usd=financial["financial_exposure_usd"],
            daily_cost_usd=financial["daily_cost_usd"],
            mitigation_cost_usd=financial["mitigation_cost_usd"],
            net_saving_if_act_now_usd=financial["net_saving_if_act_now_usd"],
            production_lines_at_risk=financial["production_lines_at_risk"],
            halt_date_estimate=financial["halt_date_estimate"],
        )


def build_advice_prompt(
    shipment,
    score_result: dict[str, Any],
    question: str | None,
) -> str:
    """Build a compact JSON prompt for LLM-owned reasoning only."""
    evidence_events = score_result.get("evidence_events", [])[:4]
    features = score_result.get("features", {})

    # shipment may be a dict (from compact_shipment_for_prompt) or a ShipmentInput
    s = shipment if isinstance(shipment, dict) else (shipment.model_dump() if hasattr(shipment, 'model_dump') else dict(shipment))

    # Build a concise feature summary highlighting what's actually driving risk
    feature_drivers = []
    inv_days = s.get("inventory_days_cover", 0)
    lead_days = s.get("lead_time_days", 0)
    delay_cnt = s.get("supplier_delay_count", 0)
    vessel_name = s.get("vessel_name", "")
    vessel_status = s.get("vessel_status", "")
    material = s.get("material", "cargo")
    origin = s.get("origin", "")
    destination = s.get("destination", "")
    supplier = s.get("supplier", "")
    eta_date = s.get("eta_date", "")
    priority = s.get("priority", "")
    declared_value = s.get("declared_value_usd", 0)

    if features.get("inventory_pressure", 0) >= 7:
        feature_drivers.append(f"inventory critically low at {inv_days} days cover")
    elif features.get("inventory_pressure", 0) >= 4:
        feature_drivers.append(f"inventory moderately tight at {inv_days} days cover")
    if features.get("priority_score", 0) >= 6:
        feature_drivers.append(f"high buyer priority ({priority})")
    if features.get("lead_time_days", 0) >= 20:
        feature_drivers.append(f"extended lead time of {lead_days} days")
    elif features.get("lead_time_days", 0) >= 14:
        feature_drivers.append(f"moderate lead time of {lead_days} days")
    if features.get("supplier_delay_count", 0) >= 3:
        feature_drivers.append(f"supplier has {delay_cnt} previous delays (unreliable)")
    elif features.get("supplier_delay_count", 0) > 0:
        feature_drivers.append(f"supplier has {delay_cnt} prior delay(s)")
    if features.get("vessel_status_score", 0) >= 5:
        feature_drivers.append(f"vessel {vessel_name} status is concerning ({vessel_status})")
    elif features.get("vessel_status_score", 0) > 0:
        feature_drivers.append(f"vessel {vessel_name} is {vessel_status}")
    if features.get("declared_value_score", 0) >= 6:
        feature_drivers.append(f"high-value cargo (${declared_value:,.0f})")
    if features.get("max_external_severity", 0) >= 7:
        feature_drivers.append("significant external disruption signals detected")

    driver_summary = "; ".join(feature_drivers) if feature_drivers else "no dominant single driver — composite risk from multiple moderate factors"

    return f"""You are a senior supply chain risk analyst at a global procurement control tower.

TASK: Analyze the shipment risk score and produce a differentiated, actionable recommendation.
The score is already computed — do NOT recalculate it. Your job is to EXPLAIN it and recommend ACTIONS.

KEY RISK DRIVERS FOR THIS SHIPMENT:
{driver_summary}

RULES FOR RECOMMENDATIONS:
1. Each action MUST be unique to this shipment's situation. Never repeat the same action across shipments.
2. Reference specific details: the material ({material}), vessel ({vessel_name or 'N/A'}), 
   route ({origin} → {destination}), supplier ({supplier}), and ETA ({eta_date}).
3. Each action starts with an owner tag: [Supplier], [Carrier], [Forwarder], [Procurement], [Plant], [Inventory], or [Compliance].
4. Each action must specify: WHO does it, WHAT exactly they do, WHEN (deadline), and WHAT TRIGGERS escalation.
5. DO NOT use generic phrases like "monitor the situation" or "keep options ready."
   Instead: specify what to monitor, what threshold triggers action, and what the fallback is.
6. For low/medium risk: focus on preventive positioning, not panic measures.
   For high risk: focus on parallel-path contingencies (backup supplier quotes, alternate routing).
   For critical risk: focus on immediate execution — approvals, expedited shipments, production line protection.

REASON WRITING RULES:
- The "reason" field must be a natural-language narrative (2-3 sentences max).
- Lead with the PRIMARY driver, then mention secondary factors.
- Do NOT just list features. Explain the BUSINESS IMPACT: what could go wrong and by when.
- Example good reason: "The {lead_days}-day lead time combined with only {inv_days} days of inventory cover means production could halt if any delay occurs. The vessel's current position suggests it may not arrive before the buffer runs out."
- Example bad reason: "Shipment is rated high due to lead time, priority, and vessel status." (too generic)

Shipment:
{json.dumps(s, indent=2)}

Quantitative score result:
{json.dumps(score_result, indent=2)}

User question:
{question or "What should we do about this shipment risk?"}

Evidence events that contributed to the risk score:
{json.dumps(evidence_events, indent=2) if evidence_events else "No evidence events matched this shipment."}

Return ONLY one compact valid JSON object with exactly these keys:
- "decision": string, one of: "proceed", "monitor", "mitigate", "hold_or_escalate"
- "reason": string, 2-3 concise sentences explaining the business impact (not just listing features)
- "recommended_actions": array of 3-5 specific, unique actions (each with owner tag, concrete task, deadline, and trigger)
- "confidence_score": integer 0-100
- "escalation_required": boolean
- "reasoning_method": "groq_analyst_review"
- "event_explanations": array of objects for each evidence event. Each object must have:
  - "event_title": string
  - "event_source": string
  - "event_severity": string
  - "risk_impact": string, 1-2 sentences on general supply chain risk
  - "shipment_connection": string, specific connection to THIS shipment's route/material/timing

Guardrails:
- Do NOT include shipment_id, risk_score, risk_level, scoring_method, model_version, signals, features, evidence_events, or context_events.
- Keep the response under 1000 words.
- If risk_level is high or critical, escalation_required must be true.
- For event_explanations, only explain events in the evidence_events list.
- No markdown, no code fences, no extra text outside the JSON."""


def compact_score_result_for_prompt(score_result: dict[str, Any]) -> dict[str, Any]:
    """Keep prompts focused while preserving all guarded model facts."""
    compacted = {
        "shipment_id": score_result.get("shipment_id"),
        "risk_score": score_result.get("risk_score"),
        "risk_level": score_result.get("risk_level"),
        "scoring_method": score_result.get("scoring_method"),
        "model_version": score_result.get("model_version"),
        "features": {k: v for k, v in score_result.get("features", {}).items() if v != 0.0},
        "signals": score_result.get("signals", [])[:8],
    }

    evidence = compact_events(score_result.get("evidence_events", []))
    if evidence:
        compacted["evidence_events"] = evidence

    context = compact_events(score_result.get("context_events", []), limit=6)
    if context:
        compacted["context_events"] = context

    return compacted


def compact_shipment_for_prompt(shipment) -> dict:
    """Filter out nulls, empty lists, and zeros to save prompt tokens."""
    data = shipment.model_dump() if hasattr(shipment, 'model_dump') else dict(shipment)
    return {
        k: v for k, v in data.items()
        if v is not None and v != [] and v != 0.0
        and k not in {'mmsi', 'flight_icao24', 'vessel_course_degrees'}
    }


def compact_events(events: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """Trim event payloads to the fields needed for reasoning."""
    compacted = []
    for event in events[:limit]:
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        compacted.append(
            {
                "source": event.get("source"),
                "title": event.get("title"),
                "summary": event.get("summary"),
                "severity": event.get("severity"),
                "event_time": event.get("event_time"),
                "location": metadata.get("location") or metadata.get("country"),
                "published": metadata.get("published"),
            }
        )
    return compacted


def extract_json_object(raw: str) -> dict[str, Any]:
    """Extract a JSON object from a model response."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in Bedrock response.")
    return json.loads(match.group(0))


def extract_response_text(response: dict[str, Any]) -> str:
    """Extract text from Bedrock Converse API response."""
    try:
        output = response.get("output", {})
        message = output.get("message", {})
        content_blocks = message.get("content", [])
        texts = [block["text"] for block in content_blocks if "text" in block]
        text = "\n".join(texts)
    except (KeyError, TypeError, IndexError) as exc:
        stop_reason = response.get("stopReason", "unknown")
        raise ValueError(f"Bedrock response text unavailable. stopReason={stop_reason}") from exc

    if text.strip():
        return text

    stop_reason = response.get("stopReason", "unknown")
    raise ValueError(f"Bedrock response was empty. stopReason={stop_reason}")


def apply_guardrails(payload: dict[str, Any], score_result: dict[str, Any]) -> dict[str, Any]:
    """Force critical fields to match model output and normalize weak fields."""
    level = score_result["risk_level"]
    payload["shipment_id"] = score_result["shipment_id"]
    payload["risk_score"] = float(score_result["risk_score"])
    payload["risk_level"] = level
    payload["scoring_method"] = score_result["scoring_method"]
    payload["model_version"] = score_result["model_version"]
    payload["signals"] = list(score_result.get("signals", []))
    payload["features"] = score_result["features"]
    payload["evidence_events"] = list(score_result.get("evidence_events", []))
    payload["context_events"] = list(score_result.get("context_events", []))
    payload["reasoning_method"] = payload.get("reasoning_method") or "bedrock_with_schema_guardrails"
    payload["escalation_required"] = level in {"high", "critical"} or bool(payload.get("escalation_required"))

    actions = payload.get("recommended_actions")
    if not isinstance(actions, list) or len(actions) < 3:
        payload["recommended_actions"] = fallback_actions(level, score_result=score_result)
    else:
        payload["recommended_actions"] = [normalize_action(action) for action in actions[:5]]

    payload["decision"] = normalize_decision(str(payload.get("decision", "")), level)
    payload["confidence_score"] = clamp_int(payload.get("confidence_score", 75), 0, 100)
    payload["reason"] = str(payload.get("reason") or "Shipment risk assessed from quantitative score and external intelligence signals.")

    explanations = payload.get("event_explanations")
    if not isinstance(explanations, list):
        explanations = []
    else:
        evidence_titles = {event.get("title", "") for event in score_result.get("evidence_events", [])}
        explanations = [
            {
                "event_title": str(exp.get("event_title", "")),
                "event_source": str(exp.get("event_source", "")),
                "event_severity": str(exp.get("event_severity", "medium")),
                "risk_impact": str(exp.get("risk_impact", "")),
                "shipment_connection": str(exp.get("shipment_connection", "")),
            }
            for exp in explanations[:5]
            if exp.get("event_title") in evidence_titles
        ]
    payload["event_explanations"] = explanations

    return payload


def normalize_decision(decision: str, level: str) -> str:
    """Normalize decision to the allowed dashboard values."""
    allowed = {"proceed", "monitor", "mitigate", "hold_or_escalate"}
    if decision in allowed:
        return decision
    return decision_for_level(level)


def normalize_action(action: Any) -> str:
    """Accept action strings or owner/action objects."""
    if isinstance(action, dict):
        owner = str(action.get("owner") or action.get("team") or action.get("role") or "").strip()
        text = str(action.get("action") or action.get("text") or action.get("recommendation") or "").strip()
        if owner and text:
            owner = owner.strip("[]")
            return f"[{owner}] {text}"
        if text:
            return text
    return str(action)


def decision_for_level(level: str) -> str:
    """Map risk level to operational decision."""
    return {
        "low": "proceed",
        "medium": "monitor",
        "high": "mitigate",
        "critical": "hold_or_escalate",
    }.get(level, "monitor")


def fallback_reason(
    *,
    shipment: ShipmentInput,
    score_result: dict[str, Any],
    level: str,
    score: float,
    signals: list[str],
) -> str:
    """Build a concise, shipment-specific narrative when the LLM is unavailable."""
    features = score_result.get("features", {})
    evidence_events = score_result.get("evidence_events", [])

    # Identify the primary driver (highest-contributing feature)
    primary = ""
    secondary = ""

    inv_pressure = features.get("inventory_pressure", 0)
    priority_score = features.get("priority_score", 0)
    lead_time = features.get("lead_time_days", 0)
    delay_count = features.get("supplier_delay_count", 0)
    vessel_score = features.get("vessel_status_score", 0)
    value_score = features.get("declared_value_score", 0)
    external_sev = features.get("max_external_severity", 0)

    # Build narrative based on dominant risk factor
    if inv_pressure >= 8:
        primary = (
            f"The shipment has a critical risk level due to only {shipment.inventory_days_cover} days of inventory cover remaining. "
            f"If {shipment.vessel_name or 'the vessel'} experiences any delay on the {shipment.origin}–{shipment.destination} route, "
            f"production lines depending on {shipment.material} could face a stockout."
        )
    elif external_sev >= 7 and evidence_events:
        event_title = evidence_events[0].get("title", evidence_events[0].get("text", ""))[:80]
        primary = (
            f"External intelligence signals indicate significant disruption risk along the route. "
            f"The matched event \"{event_title}\" could impact transit times or port operations "
            f"for this {shipment.material} shipment from {shipment.origin} to {shipment.destination}."
        )
    elif delay_count >= 3:
        primary = (
            f"Supplier {shipment.supplier} has a history of {shipment.supplier_delay_count} delivery delays, "
            f"making this {shipment.material} shipment unreliable. Combined with a {shipment.lead_time_days}-day lead time, "
            f"any additional slip could cascade into downstream production issues."
        )
    elif lead_time >= 20 and priority_score >= 6:
        primary = (
            f"The combination of a {shipment.lead_time_days}-day lead time and high buyer priority "
            f"creates vulnerability — there is limited time to react if {shipment.vessel_name or 'the vessel'} "
            f"encounters delays en route to {shipment.destination}."
        )
    elif vessel_score >= 5:
        vessel_name = shipment.vessel_name or "The vessel"
        primary = (
            f"{vessel_name}'s current status ({shipment.vessel_status}) and the ETA uncertainty "
            f"add risk to this {shipment.material} shipment. The declared value of ${shipment.declared_value_usd:,.0f} "
            f"increases the financial exposure if delivery is delayed."
        )
    elif value_score >= 6 and priority_score >= 6:
        primary = (
            f"This is a high-value shipment (${shipment.declared_value_usd:,.0f}) with elevated buyer priority, "
            f"making it sensitive to any transit disruption on the {shipment.origin}–{shipment.destination} corridor."
        )
    else:
        primary = (
            f"The shipment {shipment.shipment_id} from {shipment.origin} to {shipment.destination} "
            f"carries composite risk from multiple moderate factors including "
            f"{shipment.lead_time_days}-day lead time and {shipment.inventory_days_cover} days of stock cover."
        )

    # Add signal context if available
    if signals:
        signal_text = signals[0]
        if "weather" in signal_text.lower():
            secondary = f" Weather conditions along the route are being monitored as a potential amplifier."
        elif "trade" in signal_text.lower() or "tariff" in signal_text.lower():
            secondary = f" Trade policy developments may introduce customs or documentation delays."
        elif "vessel" in signal_text.lower():
            secondary = f" Live vessel tracking data confirms the current position and status."
        else:
            secondary = f" Live intelligence signal detected: {signal_text[:60]}."

    return primary + secondary


def fallback_actions(
    level: str,
    *,
    shipment: ShipmentInput | None = None,
    score_result: dict[str, Any] | None = None,
) -> list[str]:
    """Deterministic but shipment-specific actions when the LLM is unavailable."""
    features = (score_result or {}).get("features", {})
    context_events = (score_result or {}).get("context_events", [])
    evidence_events = (score_result or {}).get("evidence_events", [])
    actions: list[str] = []

    if not shipment:
        return [
            "[Procurement] Review shipment risk score and determine next steps.",
            "[Carrier] Confirm current shipment status and ETA.",
            "[Inventory] Verify stock levels against expected delivery date.",
        ]

    vessel_ref = shipment.vessel_name or shipment.imo_number or "the carrier"
    material = shipment.material or "the cargo"
    eta = shipment.eta_date or "the scheduled ETA"

    # Inventory-driven actions
    if features.get("inventory_pressure", 0) >= 8:
        actions.append(
            f"[Plant] Immediately audit {material} stock on hand and freeze allocation to non-critical production lines. "
            f"Report exact days-of-supply to procurement within 1 hour."
        )
    elif features.get("inventory_pressure", 0) >= 5:
        actions.append(
            f"[Inventory] Cross-check {material} consumption rate against {eta} arrival. "
            f"Flag to procurement if buffer drops below 3 days before delivery."
        )

    # Supplier reliability actions
    if features.get("supplier_delay_count", 0) >= 3:
        actions.append(
            f"[Procurement] Activate secondary supplier qualification for {material}. "
            f"Request spot-buy quote from backup vendor within 4 hours as insurance against {shipment.supplier}'s delay pattern."
        )
    elif features.get("supplier_delay_count", 0) > 0:
        actions.append(
            f"[Supplier] Request written confirmation from {shipment.supplier} that shipment {shipment.shipment_id} "
            f"is on track for {eta}. Include backup dispatch date if current schedule slips."
        )

    # Vessel/carrier-specific actions
    if shipment.transport_mode.lower().strip() == "sea":
        if features.get("vessel_status_score", 0) >= 5:
            actions.append(
                f"[Carrier] Escalate: {vessel_ref} status is {shipment.vessel_status}. "
                f"Demand revised ETA, next port call, and reason for status within 2 hours. "
                f"If no response, activate alternate carrier contingency."
            )
        else:
            actions.append(
                f"[Carrier] Confirm {vessel_ref} position and schedule adherence for the "
                f"{shipment.origin}→{shipment.destination} leg. Report any port congestion or deviation from route."
            )

    # Priority-based actions
    if features.get("priority_score", 0) >= 8:
        actions.append(
            f"[Procurement] This is a top-priority shipment. Pre-authorize expedited air freight for {material} "
            f"(up to ${min(shipment.declared_value_usd * 0.15, 50000):,.0f}) as a standby option. "
            f"Trigger if ETA slips more than 48 hours past {eta}."
        )
    elif features.get("priority_score", 0) >= 6 and features.get("lead_time_days", 0) >= 18:
        actions.append(
            f"[Procurement] Prepare split-shipment contingency: identify which portion of the {shipment.quantity} units "
            f"of {material} is most urgent. Have an expedited partial-ship quote ready within 24 hours."
        )

    # External event-driven actions
    weather_events = [e for e in evidence_events if "weather" in str(e.get("source", "")).lower() or "marine" in str(e.get("source", "")).lower()]
    trade_events = [e for e in evidence_events if "trade" in str(e.get("source", "")).lower()]
    news_events = [e for e in evidence_events if "news" in str(e.get("source", "")).lower()]

    if weather_events:
        location = weather_events[0].get("metadata", {}).get("location", "the route") if isinstance(weather_events[0].get("metadata"), dict) else "the route"
        actions.append(
            f"[Forwarder] Weather disruption detected near {location}. Provide alternate routing options "
            f"(port swap or transshipment) within 4 hours. Include cost delta and time impact for each option."
        )
    elif trade_events:
        actions.append(
            f"[Compliance] Trade policy alert on the {shipment.origin}→{shipment.destination} corridor. "
            f"Verify all customs documentation, HS codes, and certificates of origin are current. "
            f"Confirm no new tariff surcharges apply to {material} before the shipment clears customs."
        )
    elif news_events:
        event_title = news_events[0].get("title", "")[:60] or "geopolitical development"
        actions.append(
            f"[Compliance] Monitor impact of \"{event_title}\" on this route. "
            f"Prepare contingency customs documentation and verify restricted-party screening is current."
        )
    elif any("weather" in str(e.get("source", "")).lower() for e in context_events):
        actions.append(
            f"[Forwarder] Weather activity detected in the region. Monitor for route-matched alerts "
            f"and have a port-diversion plan ready for {vessel_ref} if conditions deteriorate."
        )

    # Value protection for high-value cargo
    if features.get("declared_value_score", 0) >= 7 and level in {"high", "critical"}:
        actions.append(
            f"[Procurement] High-value cargo (${shipment.declared_value_usd:,.0f}) at elevated risk. "
            f"Verify marine cargo insurance coverage and notify underwriter of potential delay claim. "
            f"Daily cost of capital at risk: ~${shipment.declared_value_usd * 0.0003:,.0f}/day."
        )

    # Ensure minimum action count with level-appropriate defaults
    if len(actions) < 3:
        if level == "critical":
            if not any("[Procurement]" in a and "escalat" in a.lower() for a in actions):
                actions.append(
                    f"[Procurement] Escalate to supply chain leadership with a 1-page brief: "
                    f"risk score {score_result.get('risk_score', 'N/A')}/10, {material} ETA {eta}, "
                    f"and recommended contingency spend. Get approval within 4 hours."
                )
        elif level == "high":
            if not any("[Procurement]" in a and "alternate" in a.lower() for a in actions):
                actions.append(
                    f"[Procurement] Identify alternate sourcing or routing for {material} as a precaution. "
                    f"Have a Plan B quote ready within 24 hours in case primary path fails."
                )
        elif level == "medium":
            actions.append(
                f"[Procurement] Set a calendar reminder to re-score {shipment.shipment_id} in 48 hours. "
                f"If score increases above 7.0, trigger the high-risk playbook for {material}."
            )
        else:
            actions.append(
                f"[Procurement] No immediate action required. Continue standard tracking for {shipment.shipment_id} "
                f"and re-evaluate if external signals change."
            )

    return actions[:5]


def fallback_confidence(level: str, score_result: dict[str, Any]) -> int:
    """Estimate confidence from score strength and matched signals."""
    base = {"low": 68, "medium": 72, "high": 78, "critical": 84}.get(level, 70)
    signal_bonus = min(len(score_result.get("signals", [])) * 3, 9)
    model_bonus = 5 if score_result.get("scoring_method") == "xgboost_model" else 0
    return min(base + signal_bonus + model_bonus, 95)


def fallback_event_explanations(
    shipment: ShipmentInput,
    score_result: dict[str, Any],
) -> list[dict[str, str]]:
    """Generate deterministic event explanations when Bedrock is unavailable."""
    explanations = []
    evidence_events = score_result.get("evidence_events", [])[:5]

    for event in evidence_events:
        source = str(event.get("source", "")).lower()
        title = event.get("title", "") or str(event.get("text", ""))[:100]
        severity = event.get("severity", "medium")
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}

        risk_impact = ""
        shipment_connection = ""

        if "weather" in source or "marine" in source:
            location = metadata.get("location") or metadata.get("country") or "the route"
            risk_impact = "Severe weather conditions can cause port delays, route diversions, or transit time extensions."
            shipment_connection = f"This shipment's route passes near {location}, where current weather conditions may affect transit."
        elif "trade" in source:
            risk_impact = "Trade restrictions and policy changes can cause customs delays, tariff increases, or border processing issues."
            shipment_connection = f"The shipment from {shipment.origin} to {shipment.destination} may face customs or tariff scrutiny due to current trade policy developments."
        elif "news" in source:
            risk_impact = "Geopolitical events and supply chain disruptions can create uncertainty around transit times and carrier availability."
            shipment_connection = f"Current global events may affect the {shipment.transport_mode} route from {shipment.origin} to {shipment.destination}."
        elif "vessel" in source:
            vessel_name = metadata.get("vessel_name") or shipment.vessel_name or "the vessel"
            status = metadata.get("status") or shipment.vessel_status or "unknown"
            risk_impact = "Vessel operational issues can cause delays, schedule changes, or require alternative routing."
            shipment_connection = f"Current status of {vessel_name} ({status}) indicates potential transit delays for this shipment."
        else:
            risk_impact = "External intelligence signals indicate potential disruption risk along the shipment route."
            shipment_connection = f"This signal is relevant to the shipment from {shipment.origin} to {shipment.destination}."

        explanations.append({
            "event_title": title,
            "event_source": event.get("source", "intelligence"),
            "event_severity": severity,
            "risk_impact": risk_impact,
            "shipment_connection": shipment_connection,
        })

    return explanations


def clamp_int(value: Any, lower: int, upper: int) -> int:
    """Clamp a value to an integer range."""
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        parsed = lower
    return max(lower, min(upper, parsed))


def classify_bedrock_error(exc: Exception) -> str:
    """Classify Bedrock failures into user-visible fallback reasons."""
    text = str(exc).lower()
    if "throttling" in text or "rate" in text or "too many requests" in text:
        return "bedrock_throttled"
    if "access denied" in text or "unauthorized" in text or "forbidden" in text or "credentials" in text or "security token" in text or "unrecognizedclient" in text:
        return "bedrock_auth_failed"
    if "model" in text and ("not found" in text or "not available" in text or "not supported" in text):
        return "bedrock_model_unavailable"
    if "timeout" in text or "connection" in text or "network" in text:
        return "bedrock_network_failed"
    if "validation" in text or "invalid" in text:
        return "bedrock_validation_error"
    return "bedrock_call_failed"
