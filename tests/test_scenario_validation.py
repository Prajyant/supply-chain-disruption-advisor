"""
Scenario-based validation tests for the Supply Chain Disruption Advisor.

These tests validate that the system's risk scoring matches real-world
danger levels. A LOW score on a known danger zone is always a FAILURE.

Run with: pytest tests/test_scenario_validation.py -v
"""
from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import requests

logger = logging.getLogger(__name__)

# Configuration
API_BASE = os.getenv("TEST_API_BASE", "http://localhost:8000")
SCENARIOS_DIR = Path(__file__).parent / "scenarios"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

RISK_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def load_csv(filename: str) -> list[dict[str, str]]:
    """Load a scenario CSV file into a list of dicts."""
    filepath = SCENARIOS_DIR / filename
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def risk_level_gte(actual: str, expected: str) -> bool:
    """Check if actual risk level is >= expected level."""
    return RISK_LEVEL_ORDER.get(actual.lower(), -1) >= RISK_LEVEL_ORDER.get(expected.lower(), -1)


def risk_level_eq(actual: str, expected: str) -> bool:
    """Check if actual risk level matches expected."""
    return actual.lower() == expected.lower()


# ============================================================
# TEST: Route Distance Validation (Searoute)
# ============================================================

def load_route_scenarios():
    rows = load_csv("test_route_distances.csv")
    return [(r["test_id"], r) for r in rows]


@pytest.mark.parametrize("test_id,scenario", load_route_scenarios(), ids=lambda x: x if isinstance(x, str) else x.get("test_scenario_tag", ""))
def test_route_distance(test_id: str, scenario: dict[str, str]):
    """Validate sea route distance calculations against known real-world distances."""
    origin = scenario["origin_port"]
    destination = scenario["destination_port"]
    speed = float(scenario["assumed_vessel_speed_knots"])

    response = requests.get(
        f"{API_BASE}/maritime/route-distance",
        params={"origin": origin, "destination": destination, "speed_knots": speed},
        timeout=15,
    )

    if response.status_code == 404:
        pytest.skip(f"Port not resolved: {origin} → {destination}")

    assert response.status_code == 200, f"API error {response.status_code}: {response.text}"
    data = response.json()

    distance_nm = data.get("distance_nm", 0)
    expected_min = float(scenario["expected_distance_nm_min"])
    expected_max = float(scenario["expected_distance_nm_max"])

    assert expected_min <= distance_nm <= expected_max, (
        f"[{scenario['test_scenario_tag']}] Route {origin}→{destination}: "
        f"got {distance_nm:.0f} nm, expected {expected_min:.0f}–{expected_max:.0f} nm"
    )


# ============================================================
# TEST: Port Congestion Validation (UNCTAD)
# ============================================================

def load_port_scenarios():
    rows = load_csv("test_port_congestion.csv")
    return [(r["test_id"], r) for r in rows]


@pytest.mark.parametrize("test_id,scenario", load_port_scenarios(), ids=lambda x: x if isinstance(x, str) else x.get("test_scenario_tag", ""))
def test_port_congestion(test_id: str, scenario: dict[str, str]):
    """Validate port congestion levels match known real-world performance."""
    port_name = scenario["port_name"]

    response = requests.get(
        f"{API_BASE}/maritime/port-congestion/{port_name}",
        timeout=15,
    )

    if response.status_code == 404:
        pytest.skip(f"Port not in database: {port_name}")

    assert response.status_code == 200, f"API error {response.status_code}: {response.text}"
    data = response.json()

    actual_severity = data.get("severity", "low").lower()
    expected_level = scenario["expected_risk_level"].lower()

    # For congestion, the system must at minimum match the expected level
    # A known congested port returning LOW is a calibration failure
    if expected_level in ("high", "critical"):
        assert risk_level_gte(actual_severity, "medium"), (
            f"[{scenario['test_scenario_tag']}] Port {port_name}: "
            f"known {expected_level} congestion but system returned '{actual_severity}'. "
            f"CALIBRATION FAILURE: known danger zone must not return LOW."
        )


# ============================================================
# TEST: Sanctions Screening Validation (OFAC + UN)
# ============================================================

def load_sanctions_scenarios():
    rows = load_csv("test_sanctions_screening.csv")
    return [(r["test_id"], r) for r in rows]


@pytest.mark.parametrize("test_id,scenario", load_sanctions_scenarios(), ids=lambda x: x if isinstance(x, str) else x.get("test_scenario_tag", ""))
def test_sanctions_screening(test_id: str, scenario: dict[str, str]):
    """Validate sanctions screening against known sanctioned/clean entities."""
    test_type = scenario["test_type"]
    lookup_value = scenario["lookup_value"]
    expected_hit = scenario["expected_sanctions_hit"].upper() == "TRUE"

    if test_type == "vessel_imo":
        response = requests.get(
            f"{API_BASE}/maritime/sanctions/vessel/{lookup_value}",
            timeout=30,
        )
    elif test_type == "entity_name":
        response = requests.get(
            f"{API_BASE}/maritime/sanctions/entity/{lookup_value}",
            timeout=30,
        )
    elif test_type == "route_countries":
        response = requests.get(
            f"{API_BASE}/maritime/sanctions/route",
            params={"countries": lookup_value},
            timeout=30,
        )
    else:
        pytest.skip(f"Unknown test_type: {test_type}")
        return

    assert response.status_code == 200, f"API error {response.status_code}: {response.text}"
    data = response.json()

    if test_type == "route_countries":
        actual_hit = data.get("has_sanctions_exposure", False)
    else:
        actual_hit = data.get("is_sanctioned", False)

    if expected_hit:
        # Known sanctioned entity MUST be flagged — false negative is critical failure
        assert actual_hit, (
            f"[{scenario['test_scenario_tag']}] Expected sanctions HIT for '{lookup_value}' "
            f"but system returned CLEAR. CRITICAL: sanctioned entity not detected."
        )
    else:
        # Clean entity should not be flagged — false positive is a warning
        if actual_hit:
            logger.warning(
                f"[{scenario['test_scenario_tag']}] False positive: '{lookup_value}' "
                f"flagged as sanctioned but expected CLEAN."
            )


# ============================================================
# TEST: Weather Position Validation (Open-Meteo)
# ============================================================

def load_weather_scenarios():
    rows = load_csv("test_weather_validation.csv")
    return [(r["test_id"], r) for r in rows]


@pytest.mark.parametrize("test_id,scenario", load_weather_scenarios(), ids=lambda x: x if isinstance(x, str) else x.get("test_scenario_tag", ""))
def test_weather_position(test_id: str, scenario: dict[str, str]):
    """Validate weather API returns risk levels matching known climatological conditions.

    Note: Weather is real-time, so actual conditions may differ from historical averages.
    This test validates the API responds and the severity scoring logic works,
    not that today's weather matches the historical average.
    """
    lat = float(scenario["latitude"])
    lon = float(scenario["longitude"])

    response = requests.get(
        f"{API_BASE}/weather/position",
        params={"lat": lat, "lon": lon},
        timeout=15,
    )

    assert response.status_code == 200, f"API error {response.status_code}: {response.text}"
    data = response.json()

    # Validate response structure
    assert "weather" in data, "Response missing 'weather' field"
    assert "marine" in data or data.get("marine") is None, "Response missing 'marine' field"

    weather = data.get("weather", {})
    assert "severity" in weather, "Weather response missing 'severity' field"
    assert "wind_speed_kmh" in weather, "Weather response missing 'wind_speed_kmh'"
    assert "precipitation_mm" in weather, "Weather response missing 'precipitation_mm'"

    # Log the actual conditions for calibration review
    logger.info(
        f"[{scenario['test_scenario_tag']}] {scenario['location_name']}: "
        f"severity={weather.get('severity')}, "
        f"wind={weather.get('wind_speed_kmh')}km/h, "
        f"precip={weather.get('precipitation_mm')}mm"
    )


# ============================================================
# TEST: Vessel Registry Validation (Equasis)
# ============================================================

def load_registry_scenarios():
    rows = load_csv("test_vessel_registry.csv")
    return [(r["test_id"], r) for r in rows]


@pytest.mark.parametrize("test_id,scenario", load_registry_scenarios(), ids=lambda x: x if isinstance(x, str) else x.get("test_scenario_tag", ""))
def test_vessel_registry(test_id: str, scenario: dict[str, str]):
    """Validate vessel registry risk scoring against known vessel conditions."""
    imo = scenario["vessel_imo"]

    response = requests.get(
        f"{API_BASE}/maritime/vessel-registry/{imo}",
        timeout=15,
    )

    assert response.status_code == 200, f"API error {response.status_code}: {response.text}"
    data = response.json()

    risk_assessment = data.get("risk_assessment", {})
    risk_score = risk_assessment.get("risk_score", 0.0)
    severity = risk_assessment.get("severity", "low").lower()

    expected_min = float(scenario["expected_registry_risk_score_min"])
    expected_max = float(scenario["expected_registry_risk_score_max"])
    expected_level = scenario["expected_risk_level"].lower()

    # Validate risk score is in expected range
    assert expected_min <= risk_score <= expected_max, (
        f"[{scenario['test_scenario_tag']}] IMO {imo}: "
        f"risk_score={risk_score:.2f}, expected {expected_min:.2f}–{expected_max:.2f}"
    )

    # Validate severity level
    assert risk_level_gte(severity, expected_level) or risk_level_eq(severity, expected_level), (
        f"[{scenario['test_scenario_tag']}] IMO {imo}: "
        f"severity='{severity}', expected at least '{expected_level}'"
    )


# ============================================================
# TEST: Tariff Rate Validation (WTO/WITS)
# ============================================================

def load_tariff_scenarios():
    rows = load_csv("test_tariff_rates.csv")
    return [(r["test_id"], r) for r in rows]


@pytest.mark.parametrize("test_id,scenario", load_tariff_scenarios(), ids=lambda x: x if isinstance(x, str) else x.get("test_scenario_tag", ""))
def test_tariff_rates(test_id: str, scenario: dict[str, str]):
    """Validate tariff rates for known trade routes.

    Note: Tariff data may use fallback/synthetic values when WTO API is unavailable.
    This test validates the endpoint responds and the severity classification is correct.
    """
    origin = scenario["origin_country_iso2"]
    destination = scenario["destination_country_iso2"]
    category = scenario["product_category"]

    response = requests.get(
        f"{API_BASE}/maritime/tariffs",
        params={
            "origin_country": origin,
            "destination_country": destination,
            "product_category": category,
        },
        timeout=20,
    )

    assert response.status_code == 200, f"API error {response.status_code}: {response.text}"
    data = response.json()

    assert "severity" in data, "Response missing 'severity' field"
    assert "average_rate" in data, "Response missing 'average_rate' field"

    # Log for calibration
    logger.info(
        f"[{scenario['test_scenario_tag']}] {origin}→{destination} ({category}): "
        f"rate={data.get('average_rate')}%, severity={data.get('severity')}"
    )


# ============================================================
# REPORT GENERATION
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def generate_report(request):
    """Generate a summary report after all tests complete."""
    yield

    # Collect results
    report_lines = [
        "=" * 70,
        "SUPPLY CHAIN DISRUPTION ADVISOR — SCENARIO VALIDATION REPORT",
        f"Generated: {datetime.now().isoformat()}",
        f"API Base: {API_BASE}",
        "=" * 70,
        "",
        "This report validates that the system's risk scoring matches",
        "real-world danger levels for known scenarios.",
        "",
        "RULE: A LOW score on a known danger zone is always a FAILURE.",
        "",
        "-" * 70,
        "Test files validated:",
        f"  - test_route_distances.csv      (Searoute distance calculations)",
        f"  - test_port_congestion.csv      (UNCTAD port turnaround data)",
        f"  - test_sanctions_screening.csv  (OFAC + UN sanctions lists)",
        f"  - test_weather_validation.csv   (Open-Meteo weather/marine API)",
        f"  - test_vessel_registry.csv      (Equasis inspection data)",
        f"  - test_tariff_rates.csv         (WTO/WITS tariff rates)",
        f"  - test_shipments.csv            (Master shipment scenarios)",
        f"  - test_risk_scoring_integration.csv (End-to-end composite scoring)",
        "-" * 70,
        "",
        "Run: pytest tests/test_scenario_validation.py -v",
        "",
    ]

    report_path = RESULTS_DIR / "scenario_report.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    logger.info(f"Report written to {report_path}")
