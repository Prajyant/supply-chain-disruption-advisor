"""Strands-compatible tools for supply chain risk orchestration."""
from __future__ import annotations

from typing import Any

from app.ingestion.trade_monitor import fetch_trade_policy_events
from app.ingestion.vessel_tracker import VesselTrackerClient
from app.ingestion.weather_monitor import fetch_weather_events
from app.ingestion.worldmonitor import (
    fetch_global_disruption_news,
    fetch_supply_chain_news,
    normalize_news_event,
)
from app.models.schemas import ShipmentInput, ShipmentRiskAdviceResponse
from app.services.gemini_advice_service import GeminiAdviceService
from app.services.shipment_risk_service import ShipmentRiskService

try:
    from strands import Agent, tool
except ImportError:
    Agent = None

    def tool(func):  # type: ignore
        return func


STRANDS_SYSTEM_PROMPT = """You are SupplyChainRiskAgent.

Your job is to orchestrate supply-chain shipment risk decisions.
Use tools in this order:
1. fetch_world_intelligence when live external context is needed.
2. track_vessel_by_imo when the shipment includes an IMO number.
3. score_shipment_risk for quantitative scoring.
4. generate_shipment_advice for final reasoned mitigation JSON.
5. validate_risk_response before returning final output.

Never invent a risk score. XGBoost or the scoring tool owns numeric scoring.
Gemini or the advice tool owns explanation and mitigation.
Return structured JSON for the dashboard."""


@tool
def fetch_world_intelligence(limit: int = 10) -> dict[str, Any]:
    """Fetch live weather, news, and trade-policy intelligence for shipment analysis."""
    weather_events = fetch_weather_events(limit=limit)
    trade_events = fetch_trade_policy_events(limit=limit)
    news_events = []

    supply_items = fetch_supply_chain_news(limit=max(1, limit // 2))
    for idx, item in enumerate(supply_items):
        news_events.append(normalize_news_event(item, idx, "news_feed"))

    global_items = fetch_global_disruption_news(limit=max(1, limit - len(news_events)))
    for idx, item in enumerate(global_items):
        news_events.append(normalize_news_event(item, idx + len(news_events), "global_news"))

    events = [*weather_events, *trade_events, *news_events[:limit]]
    return {
        "count": len(events),
        "events": events,
    }


@tool
def track_vessel_by_imo(imo_number: str) -> dict[str, Any]:
    """Fetch vessel telemetry by IMO number from the configured vessel tracker."""
    vessel = VesselTrackerClient().get_vessel_by_imo(imo_number)
    return {
        "found": vessel is not None,
        "vessel": vessel,
    }


@tool
def score_shipment_risk(
    shipment: dict[str, Any],
    intelligence_events: list[dict[str, Any]] | None = None,
    use_live_intelligence: bool = True,
) -> dict[str, Any]:
    """Score a shipment quantitatively using XGBoost when trained, otherwise heuristic features."""
    shipment_input = ShipmentInput(**shipment)
    return ShipmentRiskService().score_shipment(
        shipment=shipment_input,
        intelligence_events=intelligence_events or [],
        use_live_intelligence=use_live_intelligence,
    )


@tool
def generate_shipment_advice(
    shipment: dict[str, Any],
    score_result: dict[str, Any],
    question: str | None = None,
) -> dict[str, Any]:
    """Generate final shipment mitigation advice using Gemini with schema guardrails."""
    shipment_input = ShipmentInput(**shipment)
    advice = GeminiAdviceService().build_advice(
        shipment=shipment_input,
        score_result=score_result,
        question=question,
    )
    return advice.model_dump()


@tool
def validate_risk_response(response: dict[str, Any]) -> dict[str, Any]:
    """Validate final shipment risk advice against the dashboard response schema."""
    validated = ShipmentRiskAdviceResponse(**response)
    return {
        "valid": True,
        "response": validated.model_dump(),
    }


def build_supply_chain_agent():
    """Build the Strands agent when the SDK is installed."""
    if Agent is None:
        return None

    return Agent(
        system_prompt=STRANDS_SYSTEM_PROMPT,
        tools=[
            fetch_world_intelligence,
            track_vessel_by_imo,
            score_shipment_risk,
            generate_shipment_advice,
            validate_risk_response,
        ],
    )


def is_strands_available() -> bool:
    """Return whether the Strands SDK is available in this environment."""
    return Agent is not None
