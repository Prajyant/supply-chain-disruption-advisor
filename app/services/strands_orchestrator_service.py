"""Strands orchestration service for shipment risk workflows."""
from __future__ import annotations

import logging
import json
from typing import Any

from app.agents.supply_chain_agent import (
    build_supply_chain_agent,
    fetch_world_intelligence,
    generate_shipment_advice,
    is_strands_available,
    score_shipment_risk,
    validate_risk_response,
)
from app.models.schemas import (
    ShipmentInput,
    StrandsShipmentRiskRequest,
    StrandsShipmentRiskResponse,
)
from app.services.gemini_advice_service import GeminiAdviceService
from app.services.shipment_risk_service import ShipmentRiskService

logger = logging.getLogger(__name__)


class StrandsOrchestratorService:
    """Run the supply-chain risk workflow through Strands tools when possible."""

    def __init__(self) -> None:
        self._agent = None

    def run_shipment_risk_workflow(
        self,
        req: StrandsShipmentRiskRequest,
    ) -> StrandsShipmentRiskResponse:
        """Run scoring, reasoning, and validation as an agent workflow."""
        if req.prefer_strands_sdk and is_strands_available():
            try:
                return self._run_with_strands_tools(req)
            except Exception as exc:
                logger.warning("Strands tool orchestration failed, falling back locally: %s", exc)

        return self._run_local_workflow(req)

    def _run_with_strands_tools(
        self,
        req: StrandsShipmentRiskRequest,
    ) -> StrandsShipmentRiskResponse:
        """Use the Strands agent tool registry for deterministic orchestration."""
        agent = self._get_agent()
        shipment = req.shipment.model_dump()
        steps = []
        intelligence_events = list(req.intelligence_events)

        if req.use_live_intelligence:
            world_result = agent.tool.fetch_world_intelligence(limit=10)
            world_result = unwrap_strands_tool_result(world_result)
            intelligence_events.extend(world_result.get("events", []))
            steps.append("fetch_world_intelligence")

        if req.shipment.imo_number:
            vessel_result = agent.tool.track_vessel_by_imo(imo_number=req.shipment.imo_number)
            unwrap_strands_tool_result(vessel_result)
            steps.append("track_vessel_by_imo")

        score_result = agent.tool.score_shipment_risk(
            shipment=shipment,
            intelligence_events=intelligence_events,
            use_live_intelligence=should_fetch_live_vessel_context(req.shipment, req.use_live_intelligence),
        )
        score_result = unwrap_strands_tool_result(score_result)
        steps.append("score_shipment_risk")
        advice_result = agent.tool.generate_shipment_advice(
            shipment=shipment,
            score_result=score_result,
            question=req.question,
        )
        advice_result = unwrap_strands_tool_result(advice_result)
        steps.append("generate_shipment_advice")
        validation = agent.tool.validate_risk_response(response=advice_result)
        validation = unwrap_strands_tool_result(validation)
        steps.append("validate_risk_response")

        return StrandsShipmentRiskResponse(
            agent="SupplyChainRiskAgent",
            strands_sdk_available=True,
            orchestration_method="strands_direct_tool_calls",
            steps=steps,
            result=validation["response"],
        )

    def _run_local_workflow(
        self,
        req: StrandsShipmentRiskRequest,
    ) -> StrandsShipmentRiskResponse:
        """Local fallback that mirrors the Strands tool sequence."""
        shipment: ShipmentInput = req.shipment
        steps = []
        intelligence_events = list(req.intelligence_events)

        if req.use_live_intelligence:
            world_result = fetch_world_intelligence(limit=10)
            intelligence_events.extend(world_result.get("events", []))
            steps.append("fetch_world_intelligence")

        if req.shipment.imo_number:
            steps.append("track_vessel_by_imo")

        score_result = ShipmentRiskService().score_shipment(
            shipment=shipment,
            intelligence_events=intelligence_events,
            use_live_intelligence=should_fetch_live_vessel_context(req.shipment, req.use_live_intelligence),
        )
        steps.append("score_shipment_risk")
        advice = GeminiAdviceService().build_advice(
            shipment=shipment,
            score_result=score_result,
            question=req.question,
        )
        steps.extend(["generate_shipment_advice", "validate_risk_response"])

        return StrandsShipmentRiskResponse(
            agent="SupplyChainRiskAgent",
            strands_sdk_available=is_strands_available(),
            orchestration_method="local_mirror_of_strands_workflow",
            steps=steps,
            result=advice,
        )

    def _get_agent(self):
        if self._agent is None:
            self._agent = build_supply_chain_agent()
        if self._agent is None:
            raise RuntimeError("Strands SDK is not installed.")
        return self._agent


def unwrap_strands_tool_result(result: Any) -> Any:
    """Return the underlying JSON payload from a Strands direct tool result."""
    if not isinstance(result, dict):
        return result

    content = result.get("content")
    if not isinstance(content, list) or not content:
        return result

    first = content[0]
    if not isinstance(first, dict):
        return result

    if "json" in first:
        return first["json"]

    text = first.get("text")
    if isinstance(text, str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    return result


def should_fetch_live_vessel_context(shipment: ShipmentInput, use_live_intelligence: bool) -> bool:
    """Avoid duplicate world/news fetches while still allowing vessel lookup when needed."""
    if not use_live_intelligence:
        return False

    is_sea = shipment.transport_mode.lower().strip() == "sea"
    has_submitted_vessel_position = (
        shipment.vessel_latitude is not None
        and shipment.vessel_longitude is not None
    )
    return is_sea and not has_submitted_vessel_position
