# Test Scenarios for Supply Chain Disruption Advisor

## Overview

This directory contains CSV-based test scenarios that validate the system's risk scoring against **known real-world danger levels**. Each CSV represents a specific intelligence module and contains rows with expected outcomes based on documented maritime, trade, and geopolitical conditions.

## Core Principle

> If a scenario is inherently dangerous in the real world (a vessel sailing through a historically stormy strait, a sanctioned entity, a congested port), the system **MUST** reflect that with a HIGH or CRITICAL risk score. A LOW score on a known danger zone is always a **test FAILURE**, not a warning.

## CSV Files

| File | Tests | Endpoint(s) |
|------|-------|-------------|
| `test_shipments.csv` | 20 master shipment scenarios | `POST /shipments/risk-score`, `GET /shipments/risk-summary` |
| `test_weather_validation.csv` | 10 weather/marine positions | `GET /weather/position` |
| `test_sanctions_screening.csv` | 8 sanctions lookups | `GET /maritime/sanctions/vessel/{imo}`, `GET /maritime/sanctions/entity/{name}` |
| `test_port_congestion.csv` | 8 port congestion checks | `GET /maritime/port-congestion/{port_name}` |
| `test_tariff_rates.csv` | 8 tariff rate lookups | `GET /maritime/tariffs` |
| `test_vessel_registry.csv` | 5 vessel registry checks | `GET /maritime/vessel-registry/{imo}` |
| `test_route_distances.csv` | 8 route distance calculations | `GET /maritime/route-distance` |
| `test_risk_scoring_integration.csv` | 6 end-to-end composite scores | `POST /shipments/risk-score` |

## How to Run

### Prerequisites
- Backend running on `http://localhost:8000`
- Python packages: `pytest`, `requests`, `pandas`

### Run all scenario tests:
```bash
pytest tests/test_scenario_validation.py -v
```

### Run a specific category:
```bash
pytest tests/test_scenario_validation.py -v -k "route_distance"
pytest tests/test_scenario_validation.py -v -k "sanctions"
pytest tests/test_scenario_validation.py -v -k "port_congestion"
pytest tests/test_scenario_validation.py -v -k "weather"
pytest tests/test_scenario_validation.py -v -k "vessel_registry"
pytest tests/test_scenario_validation.py -v -k "tariff"
```

### Run against a different backend:
```bash
TEST_API_BASE=http://staging.example.com:8000 pytest tests/test_scenario_validation.py -v
```

## Interpreting Results

### PASS
The system returned a risk level and/or numeric score within the expected range for that scenario.

### FAIL
The system returned a score that does not match the known real-world danger level. This indicates a **calibration bug** — the risk scoring pipeline is not correctly reflecting reality.

### SKIP
The endpoint returned 404 (port/vessel not in database) or the test requires live API keys that aren't configured.

## How to Add New Scenarios

1. Open the relevant CSV file
2. Add a new row following the existing column format
3. Set `expected_risk_level` based on **documented real-world conditions** (not what the system currently returns)
4. Add a `test_scenario_tag` for easy identification
5. Run the tests — if the new scenario fails, the system needs calibration, not the test

### Example: Adding a new weather scenario
```csv
WX-011,Bering Sea,57.000,-175.000,12,Severe winter storm,6.0,12.0,40,65,high,Bering Sea winter storms - extreme conditions for fishing and cargo vessels,marine.wave_height_m,WEATHER_BERING_WINTER
```

## Which Scenarios Require Live API Keys

| Scenario Type | Requires Live API? | Fallback Behavior |
|---|---|---|
| Route distances | No (Searoute is local) | Always works |
| Port congestion | No (baseline data built-in) | Returns baseline values |
| Sanctions screening | No (downloads public OFAC/UN lists) | First run downloads lists |
| Weather | No (Open-Meteo is free, no key) | Returns live weather data |
| Vessel registry | Yes (Equasis account) | Returns demo/default data |
| Tariff rates | No (WTO/WITS public API) | Falls back to synthetic data |

## Report Output

After running tests, a summary report is generated at:
```
tests/results/scenario_report.txt
```

## Scenario Design Philosophy

Each scenario is chosen to test a **specific, documented real-world risk condition**:

- **Weather scenarios** use coordinates and months where historical climatological data shows dangerous conditions (e.g., Cape of Good Hope in July = gale force winds)
- **Sanctions scenarios** use real IMO numbers and entity names from publicly available OFAC SDN and UN lists
- **Port congestion scenarios** use ports with documented chronic congestion from UNCTAD Maritime Transport Review
- **Tariff scenarios** use trade routes with known punitive tariffs (Section 301, anti-dumping duties)
- **Route distances** use well-known shipping lanes with published nautical mile distances
- **Vessel registry scenarios** test the age/detention/deficiency risk scoring logic

The ground truth is **the real world**, not the system's current output.
