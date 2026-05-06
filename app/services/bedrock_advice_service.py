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
    shipment: ShipmentInput,
    score_result: dict[str, Any],
    question: str | None,
) -> str:
    """Build a compact JSON prompt for Bedrock-owned reasoning only."""
    evidence_events = score_result.get("evidence_events", [])[:4]

    return f"""You are a supply chain risk analyst.

Use the quantitative score exactly as provided. Do not invent a different score.
Explain the score and produce actionable mitigation for logistics/procurement.
Treat weather, marine weather, trade, and news as supporting context. They may
amplify risk when shipment fundamentals are already weak, but they must not be
presented as the only reason for a high-risk decision.

Advice target:
- Write recommendations for the buyer/procurement control tower to send to the
  supplier, carrier, forwarder, plant, or compliance team.
- Each recommended action must start with an owner tag: [Supplier], [Carrier],
  [Forwarder], [Procurement], [Plant], [Inventory], or [Compliance].
- Each action must include a concrete request, a timing expectation, and a
  decision trigger where appropriate. Example: "[Carrier] Confirm revised ETD,
  next port call, and ETA within 2 hours; escalate if the ETA moves by more
  than 24 hours."
- Prefer shipment-specific actions over generic monitoring. Mention the actual
  material, vessel/flight, route node, ETA, inventory cover, or supplier name.

Supply Chain Risk Context:
- News events are risky because they can cause port closures, route diversions, customs delays, labor strikes, and geopolitical disruptions that directly impact transit times and delivery reliability.
- Weather events affect supply chains by causing vessel delays, port congestion, route changes, and safety-related stoppages that extend lead times unpredictably.
- Trade policy changes (tariffs, sanctions, embargoes) create customs delays, documentation requirements, and cost increases that can halt shipments at borders.
- These external factors compound existing shipment pressures like low inventory, long lead times, and supplier delays, turning manageable risks into critical disruptions.

Shipment:
{json.dumps(compact_shipment_for_prompt(shipment), indent=2)}

Quantitative score result:
{json.dumps(score_result, indent=2)}

User question:
{question or "What should we do about this shipment risk?"}

Evidence events that contributed to the risk score:
{json.dumps(evidence_events, indent=2) if evidence_events else "No evidence events matched this shipment."}

Return ONLY one compact valid JSON object with exactly these keys:
- "decision": string, one of: "proceed", "monitor", "mitigate", "hold_or_escalate"
- "reason": string, 1-3 concise sentences
- "recommended_actions": array of 3-5 specific actions
- "confidence_score": integer 0-100
- "escalation_required": boolean
- "reasoning_method": short string such as "bedrock_analyst_review"
- "event_explanations": array of objects, one for each evidence event that contributed to the risk score. Each object must have:
  - "event_title": string, the title of the event
  - "event_source": string, the source of the event
  - "event_severity": string, the severity level
  - "risk_impact": string, 1-2 sentences explaining why this event is generally risky for supply chains
  - "shipment_connection": string, how it specifically affects this shipment's route, material, or timing

Guardrails:
- risk_score must equal the provided score.
- risk_level must match the provided level.
- Do not include shipment_id, risk_score, risk_level, scoring_method, model_version,
  signals, features, evidence_events, or context_events. The server injects those.
- Keep the whole response under 1200 words.
- Use actions that are operationally specific, not generic.
- Every recommended action must have an owner tag and a concrete artifact or
  next step, such as revised ETA, recovery plan, customs document pack, partial
  expedite quote, alternate port plan, or stock allocation decision.
- Explain shipment-owned drivers first: inventory cover, priority, lead time, supplier history, vessel status, and value.
- Mention weather/news/trade only when the score result contains matching non-zero features or evidence events.
- If risk_level is high or critical, escalation_required must be true.
- For event_explanations, only explain events that are in the evidence_events list and actually contributed to the risk score.
- No markdown, no code fences, no extra text."""


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
    """Build a concise, shipment-specific explanation when Bedrock is unavailable."""
    features = score_result.get("features", {})
    drivers = []
    if features.get("inventory_pressure", 0) >= 7:
        drivers.append(f"low inventory cover of {shipment.inventory_days_cover} days")
    if features.get("priority_score", 0) >= 6:
        drivers.append(f"{shipment.priority} buyer priority")
    if features.get("lead_time_days", 0) >= 14:
        drivers.append(f"{shipment.lead_time_days}-day lead time")
    if features.get("supplier_delay_count", 0) > 0:
        drivers.append(f"{shipment.supplier_delay_count} previous supplier delay signals")
    if features.get("vessel_status_score", 0) > 0:
        drivers.append("live vessel telemetry on the route")

    driver_text = ", ".join(drivers[:4]) if drivers else "shipment fundamentals and live route context"
    external_text = " External weather/news/trade was checked but did not materially change the score."
    if signals:
        external_text = f" Matched live signal: {signals[0]}."

    return (
        f"Shipment {shipment.shipment_id} from {shipment.origin} to {shipment.destination} is rated {level} "
        f"at {score:.2f}/10 because of {driver_text}.{external_text}"
    )


def fallback_actions(
    level: str,
    *,
    shipment: ShipmentInput | None = None,
    score_result: dict[str, Any] | None = None,
) -> list[str]:
    """Deterministic actions when Bedrock is unavailable or invalid."""
    features = (score_result or {}).get("features", {})
    context_events = (score_result or {}).get("context_events", [])
    evidence_events = (score_result or {}).get("evidence_events", [])
    actions: list[str] = []

    if shipment and features.get("inventory_pressure", 0) >= 6:
        actions.append(
            f"[Plant] Confirm exact RM stock cover for {shipment.material} within 2 hours and freeze non-critical consumption until the ETA is confirmed."
        )
    if shipment and features.get("priority_score", 0) >= 6:
        actions.append(
            f"[Procurement] Prepare an expedited split-shipment quote for the highest-priority quantity of {shipment.material}; trigger it if ETA slips by more than 24 hours."
        )
    if shipment and features.get("supplier_delay_count", 0) > 0:
        actions.append(
            f"[Supplier] Send a written recovery plan from {shipment.supplier} today, including backup dispatch date, alternate carrier, and escalation contact."
        )
    if shipment and shipment.transport_mode.lower().strip() == "sea":
        actions.append(
            f"[Carrier] Confirm live vessel position, next port call, port status, and revised ETA for {shipment.vessel_name or shipment.imo_number or shipment.shipment_id} within 2 hours."
        )
    if any("weather" in str(event.get("source", "")).lower() or "marine" in str(event.get("source", "")).lower() for event in evidence_events):
        actions.append("[Forwarder] Provide alternate port, transshipment, or holding-plan options because route-matched weather is affecting the risk score.")
    elif any("weather" in str(event.get("source", "")).lower() or "marine" in str(event.get("source", "")).lower() for event in context_events):
        actions.append("[Forwarder] Keep live weather and marine alerts on watch; propose reroute only if the alert becomes route-matched or carrier revises ETA.")
    if any("trade" in str(event.get("source", "")).lower() or "news" in str(event.get("source", "")).lower() for event in evidence_events):
        actions.append("[Compliance] Verify customs documents, tariff exposure, and restricted-party checks before the shipment reaches the next border or port.")
    elif any("trade" in str(event.get("source", "")).lower() or "news" in str(event.get("source", "")).lower() for event in context_events):
        actions.append("[Compliance] Review World Monitor headlines for customs or trade-policy relevance; act only if they match the route or material.")

    if len(actions) >= 3:
        return actions[:5]

    if level == "critical":
        actions.extend([
            "[Procurement] Escalate to logistics leadership immediately with risk score, ETA, and inventory-cover impact.",
            "[Supplier] Check alternate supplier or route availability before dispatch.",
            "[Inventory] Increase buffer stock or allocate available stock to dependent production lines.",
            "[Carrier] Send shipment status confirmation within 24 hours.",
        ])
    if level == "high":
        actions.extend([
            "[Carrier] Confirm schedule and route exposure before shipment release.",
            "[Procurement] Prepare alternate routing or backup supplier options.",
            "[Forwarder] Increase monitoring cadence until the shipment clears the risky node.",
        ])
    if level == "medium":
        actions.extend([
            "[Forwarder] Monitor route conditions daily until delivery.",
            "[Inventory] Confirm inventory cover against expected arrival date.",
            "[Procurement] Keep a backup logistics option ready if signals worsen.",
        ])
    if not actions:
        actions.extend([
            "[Procurement] Proceed with the current shipment plan.",
            "[Supplier] Continue normal supplier and carrier monitoring.",
            "[Procurement] Re-score if weather, trade, or supplier signals change.",
        ])
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
