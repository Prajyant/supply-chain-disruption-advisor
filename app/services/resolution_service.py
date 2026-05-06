import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import os

from app.models.schemas import (
    ShipmentInput,
    ShipmentRiskResponse,
    ResolutionPackage,
    ResolutionEmail,
    CFOSummary,
)

logger = logging.getLogger(__name__)


def calculate_financial_impact(shipment: ShipmentInput, score_result: ShipmentRiskResponse) -> Dict[str, float]:
    """Calculate the financial impact of a disruption."""
    # Determine unit value based on material type
    material_lower = shipment.material.lower()
    if "electronic" in material_lower or "chip" in material_lower:
        unit_value = 50.0
    elif "copper" in material_lower or "metal" in material_lower or "steel" in material_lower:
        unit_value = 8.0
    elif "chemical" in material_lower or "plastic" in material_lower:
        unit_value = 12.0
    else:
        unit_value = 20.0

    # If user provided declared value, we use that to derive a more accurate unit value
    if getattr(shipment, "declared_value_usd", 0.0) > 0 and shipment.quantity > 0:
        actual_unit_value = shipment.declared_value_usd / shipment.quantity
        unit_value = actual_unit_value

    risk_score_multiplier = score_result.get("risk_score", 0) / 10.0
    financial_exposure_usd = shipment.quantity * unit_value * risk_score_multiplier

    inventory_days = getattr(shipment, "inventory_days_cover", 0)
    if inventory_days > 0:
        daily_cost_usd = financial_exposure_usd / inventory_days
    else:
        daily_cost_usd = financial_exposure_usd / 30.0

    return {
        "financial_exposure_usd": financial_exposure_usd,
        "daily_cost_usd": daily_cost_usd,
        "unit_value": unit_value
    }


class ResolutionService:
    """Service to generate resolution packages using deterministic logic."""

    def __init__(self):
        pass

    def generate_resolution_package(
        self,
        shipment: ShipmentInput,
        score_result: ShipmentRiskResponse,
        financial_impact: Dict[str, float]
    ) -> ResolutionPackage:
        """Generate a complete resolution package."""
        return self._fallback_resolution(shipment, score_result, financial_impact)

    def _fallback_resolution(
        self,
        shipment: ShipmentInput,
        score_result,
        financial_impact: Dict[str, float]
    ) -> ResolutionPackage:
        """Generate a realistic resolution package."""
        exposure_formatted = f"${financial_impact['financial_exposure_usd']:,.0f}"
        vessel = getattr(shipment, "vessel_name", None) or "the assigned vessel"
        risk_level = score_result.get("risk_level", "high") if isinstance(score_result, dict) else getattr(score_result, "risk_level", "high")
        risk_score = score_result.get("risk_score", 7) if isinstance(score_result, dict) else getattr(score_result, "risk_score", 7)
        signals = score_result.get("signals", []) if isinstance(score_result, dict) else getattr(score_result, "signals", [])
        
        return ResolutionPackage(
            shipment_id=shipment.shipment_id,
            risk_level=risk_level,
            generated_at=datetime.now(timezone.utc),
            carrier_email=ResolutionEmail(
                to="Carrier Operations Team",
                subject=f"URGENT: Status Update Required - Shipment {shipment.shipment_id}",
                body=f"Team,\n\nWe are tracking severe risk signals regarding {vessel} on the route from {shipment.origin} to {shipment.destination}. Please provide an immediate update on the current ETA and your proposed recovery plan for the {shipment.quantity} units of {shipment.material} onboard.\n\nRegards,\nSupply Chain Control Tower",
                priority="urgent",
                send_within_hours=2
            ),
            alternate_supplier_email=ResolutionEmail(
                to="Key Account Manager (Alternate Supplier)",
                subject="Capacity Planning Inquiry: Upcoming Quarter",
                body=f"Hello,\n\nAs part of our standard capacity planning, we are reviewing our allocation for {shipment.material}. Could you confirm your current lead times and available spot capacity for a potential volume of {shipment.quantity} units out of {shipment.destination}?\n\nBest,\nProcurement Team",
                priority="normal",
                send_within_hours=24
            ),
            internal_escalation_email=ResolutionEmail(
                to="Director of Supply Chain & Head of Procurement",
                subject=f"High Risk Alert: {shipment.shipment_id} - ${financial_impact['financial_exposure_usd']:,.0f} Exposure",
                body=f"Leadership,\n\nShipment {shipment.shipment_id} ({shipment.material}) from {shipment.supplier} is currently assessed at a {risk_score}/10 risk level. Our financial exposure is {exposure_formatted} with only {getattr(shipment, 'inventory_days_cover', 0)} days of inventory cover remaining. I recommend we immediately engage the alternate supplier for spot capacity.\n\nPlease advise if approved.",
                priority="urgent",
                send_within_hours=1
            ),
            cfo_summary=CFOSummary(
                headline=f"Immediate supply chain disruption threatens {exposure_formatted} in working capital.",
                exposure_usd=financial_impact['financial_exposure_usd'],
                recommended_action="Approve expedited spot buy from secondary supplier to maintain production.",
                decision_deadline="Within 24 hours",
                key_facts=[
                    f"Shipment {shipment.shipment_id} ({shipment.material}) severely impacted en route to {shipment.destination}.",
                    f"Current inventory cover is only {getattr(shipment, 'inventory_days_cover', 0)} days.",
                    f"Daily cost of disruption estimated at ${financial_impact['daily_cost_usd']:,.0f}.",
                    f"Primary risk signals: {', '.join(signals[:2]) if signals else 'Logistics delays'}."
                ]
            )
        )
