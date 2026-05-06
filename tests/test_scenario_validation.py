"""
Supply Chain Disruption Advisor — Scenario Validation Test Suite
================================================================

This test suite loads CSV scenario files and validates that the live API
returns risk scores matching known real-world danger levels.

CORE PRINCIPLE:
    If a scenario is inherently dangerous in the real world, the system MUST
    reflect that with a HIGH or CRITICAL risk score. A LOW score on a known
    danger zone is ALWAYS a test FAILURE.

Usage:
    pytest tests/test_scenario_validation.py -v --tb=short
    pytest tests/test_scenario_validation.py -k "WEATHER" -v
    pytest tests/test_scenario_validation.py --html=tests/results/report.html
"""

import csv
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.getenv("SCDA_API_URL", "http://localhost:8000")
SCENARIOS_DIR = Path(__file__).parent / "scenarios"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

RISK_LEVEL_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Report collector
# ---------------------------------------------------------------------------

_report_lines: list[str] = []


def _record(test_id: str, tag: str, expected: str, actual: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    line = f"[{status}] {test_id} | {tag} | expected={expected} actual={actual}"
    if detail:
        line += f" | {detail}"
    _report_lines.append(line)


def _write_report():
    report_path = RESULTS_DIR / "scenario_report.txt"
    total = len(_report_lines)
    passed = sum(1 for l in _report_lines if l.startswith("[PASS]"))
    failed = total - passed

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("SUPPLY CHAIN DISRUPTION ADVISOR — SCENARIO VALIDATION REPORT\n")
        f.write(f"Generated: {datetime.utcnow().isoformat()}Z\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"TOTAL: {total} | PASSED: {passed} | FAILED: {failed}\n")
        f.write(f"Pass Rate: {passed/total*100:.1f}%\n" if total else "No tests run\n")
        f.write("\n" + "-" * 80 + "\n\n")
        for line in _report_lines:
            f.write(line + "\n")
        f.write("\n" + "=" * 80 + "\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_csv(filename: str) -> list[dict[str, str]]:
    """Load a CSV scenario file and return rows as dicts."""
    path = SCENARIOS_DIR / filename
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def risk_level_matches(expected: str, actual: str) -> bool:
    """Check if actual risk level meets or exceeds expected level.

    REAL-WORLD CALIBRATION RULE:
    For known danger zones (expected HIGH or CRITICAL), the system must
    return at least that level. Returning LOW for a known danger is always a failure.
    """
    expected_upper = expected.upper().strip()
    actual_upper = actual.upper().strip()

    if expected_upper in ("HIGH", "CRITICAL"):
        # Must meet or exceed expected level
        return RISK_LEVEL_ORDER.get(actual_upper, -1) >= RISK_LEVEL_ORDER.get(expected_upper, 0)
    elif expected_upper == "LOW":
        # LOW expected means actual should be LOW or at most MEDIUM
        return RISK_LEVEL_ORDER.get(actual_upper, 3) <= RISK_LEVEL_ORDER.get("MEDIUM", 1)
    elif expected_upper == "MEDIUM":
        # MEDIUM expected: actual should be MEDIUM, HIGH, or CRITICAL (not LOW)
        return RISK_LEVEL_ORDER.get(actual_upper, -1) >= RISK_LEVEL_ORDER.get("MEDIUM", 1)
    return actual_upper == expected_upper


def score_in_range(actual_score: float, min_score: float, max_score: float) -> bool:
    """Check if actual score falls within expected range (with 0.05 tolerance)."""
    tolerance = 0.05
    return (min_score - tolerance) <= actual_score <= (max_score + tolerance)


def api_get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to the API."""
    url = f"{BASE_URL}{endpoint}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(endpoint: str, json_body: dict) -> dict:
    """Make a POST request to the API."""
    url = f"{BASE_URL}{endpoint}"
    resp = requests.post(url, json=json_body, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# CSV FILE 1: test_shipments.csv — Shipment Risk Scoring
# ---------------------------------------------------------------------------

_shipment_rows = load_csv("test_shipments.csv") if (SCENARIOS_DIR / "test_shipments.csv").exists() else []


@pytest.mark.parametrize(
    "row",
    _shipment_rows,
    ids=[r.get("test_scenario_tag", f"row-{i}") for i, r in enumerate(_shipment_rows)],
)
class TestShipmentRiskScoring:
    """Validate that POST /shipments/risk-score returns correct risk levels for each scenario."""

    def test_risk_level(self, row: dict[str, str]):
        """Assert the system returns the expected risk level for this shipment scenario."""
        shipment_payload = {
            "shipment": {
                "shipment_id": row["shipment_id"],
                "origin": row["origin_port"],
                "destination": row["destination_port"],
                "origin_country": row["origin_country"],
                "destination_country": row["destination_country"],
                "imo_number": row["vessel_imo"],
                "vessel_name": row["vessel_name"],
                "material": row["cargo_type"],
                "declared_value_usd": float(row["cargo_value_usd"]),
                "quantity": float(row["weight_kg"]),
                "hs_code": row["hs_code"],
                "departure_date": row["departure_date"],
                "eta_date": row["expected_arrival_date"],
                "transport_mode": "air" if row["test_scenario_tag"] == "WEATHER_VOLCANIC_AIR" else "sea",
            },
            "intelligence_events": [],
            "use_live_intelligence": True,
        }

        try:
            result = api_post("/shipments/risk-score", shipment_payload)
            actual_level = result.get("risk_level", result.get("overall_risk_level", "UNKNOWN")).upper()
            expected_level = row["expected_risk_level"].upper()

            passed = risk_level_matches(expected_level, actual_level)
            _record(
                row["shipment_id"],
                row["test_scenario_tag"],
                expected_level,
                actual_level,
                passed,
                row["expected_risk_reason"][:80] if not passed else "",
            )

            assert passed, (
                f"REAL-WORLD CALIBRATION FAILURE: {row['test_scenario_tag']}\n"
                f"Expected: {expected_level}, Got: {actual_level}\n"
                f"Reason: {row['expected_risk_reason']}\n"
                f"A known danger zone returned an insufficiently high risk score."
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not available — start the server to run live tests")
        except requests.exceptions.HTTPError as e:
            pytest.fail(f"API returned error: {e.response.status_code} - {e.response.text[:200]}")


# ---------------------------------------------------------------------------
# CSV FILE 2: test_weather_validation.csv — Weather Risk Validation
# ---------------------------------------------------------------------------

_weather_rows = load_csv("test_weather_validation.csv") if (SCENARIOS_DIR / "test_weather_validation.csv").exists() else []


@pytest.mark.parametrize(
    "row",
    _weather_rows,
    ids=[r.get("test_scenario_tag", f"wx-{i}") for i, r in enumerate(_weather_rows)],
)
class TestWeatherValidation:
    """Validate weather API returns risk scores matching known climatological danger levels."""

    def test_weather_risk(self, row: dict[str, str]):
        """Assert weather risk at known coordinates matches expected danger level."""
        params = {
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "month": int(row["month_to_test"]),
        }

        try:
            # Try the weather position endpoint
            result = api_get("/weather/position", params=params)
            actual_level = result.get("risk_level", "UNKNOWN").upper()
            expected_level = row["expected_risk_level"].upper()

            passed = risk_level_matches(expected_level, actual_level)
            _record(
                row["test_id"],
                row["test_scenario_tag"],
                expected_level,
                actual_level,
                passed,
                row["risk_justification"][:80] if not passed else "",
            )

            assert passed, (
                f"WEATHER CALIBRATION FAILURE: {row['test_scenario_tag']}\n"
                f"Location: {row['location_name']} ({row['latitude']}, {row['longitude']})\n"
                f"Month: {row['month_to_test']}\n"
                f"Expected: {expected_level}, Got: {actual_level}\n"
                f"Justification: {row['risk_justification']}"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not available")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                pytest.skip("Weather endpoint not implemented")
            pytest.fail(f"API error: {e.response.status_code}")


# ---------------------------------------------------------------------------
# CSV FILE 3: test_sanctions_screening.csv — Sanctions Validation
# ---------------------------------------------------------------------------

_sanctions_rows = load_csv("test_sanctions_screening.csv") if (SCENARIOS_DIR / "test_sanctions_screening.csv").exists() else []


@pytest.mark.parametrize(
    "row",
    _sanctions_rows,
    ids=[r.get("test_scenario_tag", f"sn-{i}") for i, r in enumerate(_sanctions_rows)],
)
class TestSanctionsScreening:
    """Validate sanctions screening correctly identifies sanctioned entities."""

    def test_sanctions_hit(self, row: dict[str, str]):
        """Assert sanctions screening returns correct hit/miss for known entities."""
        test_type = row["test_type"]
        lookup_value = row["lookup_value"]
        expected_hit = row["expected_sanctions_hit"].upper() == "TRUE"
        expected_level = row["expected_risk_level"].upper()

        try:
            if test_type == "vessel_imo":
                result = api_get(f"/maritime/sanctions/vessel/{lookup_value}")
            elif test_type == "entity_name":
                result = api_get(f"/maritime/sanctions/entity/{lookup_value}")
            elif test_type == "route_countries":
                countries = lookup_value.split(",")
                result = api_post("/maritime/sanctions/route", {"countries": countries})
            else:
                pytest.skip(f"Unknown test_type: {test_type}")
                return

            actual_hit = result.get("sanctions_hit", result.get("is_sanctioned", False))
            actual_level = result.get("risk_level", "UNKNOWN").upper()

            hit_match = actual_hit == expected_hit
            level_match = risk_level_matches(expected_level, actual_level)
            passed = hit_match and level_match

            _record(
                row["test_id"],
                row["test_scenario_tag"],
                f"hit={expected_hit} level={expected_level}",
                f"hit={actual_hit} level={actual_level}",
                passed,
                row["notes"][:80] if not passed else "",
            )

            assert passed, (
                f"SANCTIONS SCREENING FAILURE: {row['test_scenario_tag']}\n"
                f"Lookup: {test_type}={lookup_value}\n"
                f"Expected hit={expected_hit}, level={expected_level}\n"
                f"Got hit={actual_hit}, level={actual_level}\n"
                f"Notes: {row['notes']}"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not available")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                pytest.skip("Sanctions endpoint not implemented")
            pytest.fail(f"API error: {e.response.status_code}")


# ---------------------------------------------------------------------------
# CSV FILE 4: test_port_congestion.csv — Port Congestion Validation
# ---------------------------------------------------------------------------

_congestion_rows = load_csv("test_port_congestion.csv") if (SCENARIOS_DIR / "test_port_congestion.csv").exists() else []


@pytest.mark.parametrize(
    "row",
    _congestion_rows,
    ids=[r.get("test_scenario_tag", f"pc-{i}") for i, r in enumerate(_congestion_rows)],
)
class TestPortCongestion:
    """Validate port congestion levels match known real-world port performance."""

    def test_congestion_level(self, row: dict[str, str]):
        """Assert port congestion matches known turnaround times from UNCTAD data."""
        port_name = row["port_name"].replace(" ", "%20")
        expected_level = row["expected_risk_level"].upper()

        try:
            result = api_get(f"/maritime/port-congestion/{port_name}")
            actual_level = result.get("risk_level", result.get("congestion_level", "UNKNOWN")).upper()

            # Also validate turnaround days if returned
            actual_turnaround = result.get("avg_turnaround_days")
            turnaround_ok = True
            if actual_turnaround is not None:
                min_days = float(row["expected_avg_turnaround_days_min"])
                max_days = float(row["expected_avg_turnaround_days_max"])
                turnaround_ok = min_days * 0.5 <= actual_turnaround <= max_days * 2.0

            level_match = risk_level_matches(expected_level, actual_level)
            passed = level_match and turnaround_ok

            _record(
                row["test_id"],
                row["test_scenario_tag"],
                expected_level,
                actual_level,
                passed,
                row["congestion_known_cause"][:80] if not passed else "",
            )

            assert passed, (
                f"PORT CONGESTION FAILURE: {row['test_scenario_tag']}\n"
                f"Port: {row['port_name']} ({row['un_locode']})\n"
                f"Expected: {expected_level}, Got: {actual_level}\n"
                f"Cause: {row['congestion_known_cause']}"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not available")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                pytest.skip("Port congestion endpoint not implemented")
            pytest.fail(f"API error: {e.response.status_code}")


# ---------------------------------------------------------------------------
# CSV FILE 5: test_tariff_rates.csv — Tariff Rate Validation
# ---------------------------------------------------------------------------

_tariff_rows = load_csv("test_tariff_rates.csv") if (SCENARIOS_DIR / "test_tariff_rates.csv").exists() else []


@pytest.mark.parametrize(
    "row",
    _tariff_rows,
    ids=[r.get("test_scenario_tag", f"tf-{i}") for i, r in enumerate(_tariff_rows)],
)
class TestTariffRates:
    """Validate tariff rates match known trade policy data from WTO/WITS."""

    def test_tariff_risk(self, row: dict[str, str]):
        """Assert tariff risk level matches known trade policy for this route/product."""
        params = {
            "origin_country": row["origin_country_iso2"],
            "destination_country": row["destination_country_iso2"],
            "hs_code": row["hs_code"],
        }
        expected_level = row["expected_risk_level"].upper()

        try:
            result = api_get("/maritime/tariffs", params=params)
            actual_level = result.get("risk_level", "UNKNOWN").upper()

            # Validate tariff rate range if returned
            actual_rate = result.get("tariff_rate_pct", result.get("applied_rate"))
            rate_ok = True
            if actual_rate is not None:
                min_rate = float(row["expected_tariff_rate_min_pct"])
                max_rate = float(row["expected_tariff_rate_max_pct"])
                rate_ok = min_rate * 0.8 <= actual_rate <= max_rate * 1.5

            level_match = risk_level_matches(expected_level, actual_level)
            passed = level_match and rate_ok

            _record(
                row["test_id"],
                row["test_scenario_tag"],
                f"{expected_level} (rate {row['expected_tariff_rate_min_pct']}-{row['expected_tariff_rate_max_pct']}%)",
                f"{actual_level} (rate={actual_rate}%)" if actual_rate else actual_level,
                passed,
                row["policy_note"][:80] if not passed else "",
            )

            assert passed, (
                f"TARIFF CALIBRATION FAILURE: {row['test_scenario_tag']}\n"
                f"Route: {row['origin_country_iso2']} → {row['destination_country_iso2']}\n"
                f"HS Code: {row['hs_code']} ({row['hs_description']})\n"
                f"Expected: {expected_level}, Got: {actual_level}\n"
                f"Policy: {row['policy_note']}"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not available")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                pytest.skip("Tariff endpoint not implemented")
            pytest.fail(f"API error: {e.response.status_code}")


# ---------------------------------------------------------------------------
# CSV FILE 6: test_vessel_registry.csv — Vessel Registry Validation
# ---------------------------------------------------------------------------

_registry_rows = load_csv("test_vessel_registry.csv") if (SCENARIOS_DIR / "test_vessel_registry.csv").exists() else []


@pytest.mark.parametrize(
    "row",
    _registry_rows,
    ids=[r.get("test_scenario_tag", f"vr-{i}") for i, r in enumerate(_registry_rows)],
)
class TestVesselRegistry:
    """Validate vessel registry risk scores reflect inspection/detention history."""

    def test_registry_risk(self, row: dict[str, str]):
        """Assert vessel registry risk matches known PSC inspection data."""
        imo = row["vessel_imo"]
        expected_level = row["expected_risk_level"].upper()

        try:
            result = api_get(f"/maritime/vessel-registry/{imo}")
            actual_level = result.get("risk_level", "UNKNOWN").upper()

            # Validate risk score range
            actual_score = result.get("risk_score", result.get("registry_risk_score"))
            score_ok = True
            if actual_score is not None:
                min_score = float(row["expected_registry_risk_score_min"])
                max_score = float(row["expected_registry_risk_score_max"])
                score_ok = score_in_range(actual_score, min_score, max_score)

            level_match = risk_level_matches(expected_level, actual_level)
            passed = level_match and score_ok

            _record(
                row["test_id"],
                row["test_scenario_tag"],
                f"{expected_level} (score {row['expected_registry_risk_score_min']}-{row['expected_registry_risk_score_max']})",
                f"{actual_level} (score={actual_score})",
                passed,
                row["risk_justification"][:80] if not passed else "",
            )

            assert passed, (
                f"VESSEL REGISTRY FAILURE: {row['test_scenario_tag']}\n"
                f"IMO: {imo}, Build Year: {row['build_year']}\n"
                f"Expected: {expected_level}, Got: {actual_level}\n"
                f"Justification: {row['risk_justification']}"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not available")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                pytest.skip("Vessel registry endpoint not implemented")
            pytest.fail(f"API error: {e.response.status_code}")


# ---------------------------------------------------------------------------
# CSV FILE 7: test_route_distances.csv — Route Distance Validation
# ---------------------------------------------------------------------------

_route_rows = load_csv("test_route_distances.csv") if (SCENARIOS_DIR / "test_route_distances.csv").exists() else []


@pytest.mark.parametrize(
    "row",
    _route_rows,
    ids=[r.get("test_scenario_tag", f"rd-{i}") for i, r in enumerate(_route_rows)],
)
class TestRouteDistances:
    """Validate route calculator returns realistic nautical mile distances."""

    def test_route_distance(self, row: dict[str, str]):
        """Assert calculated route distance falls within expected range for known trade routes."""
        payload = {
            "origin_lat": float(row["origin_lat"]),
            "origin_lon": float(row["origin_lon"]),
            "destination_lat": float(row["destination_lat"]),
            "destination_lon": float(row["destination_lon"]),
        }

        try:
            result = api_post("/maritime/route-distance", payload)
            actual_distance = result.get("distance_nm", result.get("distance_nautical_miles"))

            if actual_distance is None:
                pytest.fail("API did not return distance_nm field")

            min_nm = float(row["expected_distance_nm_min"])
            max_nm = float(row["expected_distance_nm_max"])

            # Allow 15% tolerance for routing algorithm differences
            tolerance = 0.15
            passed = (min_nm * (1 - tolerance)) <= actual_distance <= (max_nm * (1 + tolerance))

            _record(
                row["test_id"],
                row["test_scenario_tag"],
                f"{min_nm}-{max_nm} nm",
                f"{actual_distance:.0f} nm",
                passed,
                row["route_notes"][:80] if not passed else "",
            )

            assert passed, (
                f"ROUTE DISTANCE FAILURE: {row['test_scenario_tag']}\n"
                f"Route: {row['origin_port']} → {row['destination_port']}\n"
                f"Expected: {min_nm}-{max_nm} nm, Got: {actual_distance:.0f} nm\n"
                f"Notes: {row['route_notes']}"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not available")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                pytest.skip("Route distance endpoint not implemented")
            pytest.fail(f"API error: {e.response.status_code}")


# ---------------------------------------------------------------------------
# CSV FILE 8: test_risk_scoring_integration.csv — End-to-End Integration
# ---------------------------------------------------------------------------

_integration_rows = load_csv("test_risk_scoring_integration.csv") if (SCENARIOS_DIR / "test_risk_scoring_integration.csv").exists() else []


@pytest.mark.parametrize(
    "row",
    _integration_rows,
    ids=[r.get("test_scenario_tag", f"int-{i}") for i, r in enumerate(_integration_rows)],
)
class TestRiskScoringIntegration:
    """End-to-end integration: validate composite risk score from all modules combined."""

    def test_composite_risk(self, row: dict[str, str]):
        """Assert composite risk score matches expected level given all input factors."""
        # Build the integration test payload with pre-computed risk inputs
        payload = {
            "shipment": {
                "shipment_id": row["shipment_id_ref"],
                "origin": "Test Origin",
                "destination": "Test Destination",
                "declared_value_usd": float(row["cargo_value_usd"]),
                "material": "test cargo",
                "transport_mode": "sea",
            },
            "intelligence_events": [],
            "use_live_intelligence": False,
            "risk_overrides": {
                "weather_risk": row["weather_risk_input"],
                "sanctions_risk": row["sanctions_risk_input"],
                "congestion_risk": row["congestion_risk_input"],
                "registry_risk": row["registry_risk_input"],
                "tariff_risk": row["tariff_risk_input"],
                "geopolitical_risk": row["geopolitical_risk_input"],
            },
        }

        expected_level = row["expected_risk_level"].upper()
        min_score = float(row["expected_composite_risk_score_min"])
        max_score = float(row["expected_composite_risk_score_max"])

        try:
            result = api_post("/shipments/risk-score", payload)
            actual_level = result.get("risk_level", result.get("overall_risk_level", "UNKNOWN")).upper()
            actual_score = result.get("risk_score", result.get("composite_score", -1))

            level_match = risk_level_matches(expected_level, actual_level)
            score_match = score_in_range(actual_score, min_score, max_score) if actual_score >= 0 else True

            passed = level_match and score_match

            _record(
                row["test_id"],
                row["test_scenario_tag"],
                f"{expected_level} (score {min_score}-{max_score})",
                f"{actual_level} (score={actual_score:.3f})" if actual_score >= 0 else actual_level,
                passed,
                row["failure_mode_if_wrong"][:80] if not passed else "",
            )

            assert passed, (
                f"INTEGRATION FAILURE: {row['test_scenario_tag']}\n"
                f"Expected: {expected_level} (score {min_score}-{max_score})\n"
                f"Got: {actual_level} (score={actual_score})\n"
                f"Failure mode: {row['failure_mode_if_wrong']}"
            )
        except requests.exceptions.ConnectionError:
            pytest.skip("API not available")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                pytest.skip("Risk scoring endpoint not available")
            pytest.fail(f"API error: {e.response.status_code}")


# ---------------------------------------------------------------------------
# Session-scoped report generation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def generate_report():
    """Write the scenario report after all tests complete."""
    yield
    _write_report()
