# Test Scenarios — Supply Chain Disruption Advisor

## Overview

This directory contains CSV-based test scenarios that validate the Supply Chain Disruption Advisor's risk scoring against known real-world conditions. Each CSV file targets a specific intelligence module and contains rows representing carefully chosen scenarios with ground-truth expected outcomes.

## Core Principle: Real-World Calibration

> If a scenario is inherently dangerous in the real world (a vessel sailing through a historically stormy strait, a sanctioned entity, a congested port), the system **MUST** reflect that with a HIGH or CRITICAL risk score. If the system returns LOW for a known danger zone, **that is a bug**.

This ensures the platform stays calibrated to real-world risk and does not drift toward false safety.

---

## CSV Files

| File | Tests | Endpoint(s) |
|------|-------|-------------|
| `test_shipments.csv` | Master shipment registry with 20 scenarios covering weather, sanctions, congestion, registry, tariff, geopolitical, and combined risks | `POST /shipments/risk-score`, `POST /shipments/resolution-package`, `GET /shipments` |
| `test_weather_validation.csv` | 10 locations with known climatological danger levels (storms, typhoons, monsoons, calm baselines) | `GET /weather/position`, `GET /weather/route` |
| `test_sanctions_screening.csv` | 8 scenarios testing OFAC SDN, UN Security Council, and country-level sanctions screening | `GET /maritime/sanctions/vessel/{imo}`, `GET /maritime/sanctions/entity/{name}` |
| `test_port_congestion.csv` | 8 ports with known congestion levels from UNCTAD data | `GET /maritime/port-congestion/{port_name}` |
| `test_tariff_rates.csv` | 8 trade routes with known tariff rates (Section 301, USMCA, anti-dumping, MFN) | `GET /maritime/tariffs` |
| `test_vessel_registry.csv` | 5 vessels ranging from new/compliant to old/detained, plus unknown vessel handling | `GET /maritime/vessel-registry/{imo}` |
| `test_route_distances.csv` | 8 trade routes with known nautical mile distances and ETAs | `POST /maritime/route-distance` |
| `test_risk_scoring_integration.csv` | 6 end-to-end integration scenarios combining all risk factors | `POST /shipments/risk-score` |

---

## How to Run

### Prerequisites

```bash
pip install pytest requests pandas
```

### Run All Scenarios

```bash
# Start the API server first
cd supply-chain-disruption-advisor
uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, run the tests
pytest tests/test_scenario_validation.py -v --tb=short
```

### Run Specific Scenario Categories

```bash
# Weather scenarios only
pytest tests/test_scenario_validation.py -k "WEATHER" -v

# Sanctions scenarios only
pytest tests/test_scenario_validation.py -k "SANCTIONS" -v

# Integration tests only
pytest tests/test_scenario_validation.py -k "INTEGRATION" -v

# A single scenario by tag
pytest tests/test_scenario_validation.py -k "GEO_RED_SEA" -v
```

### Custom API URL

```bash
# Point to a different server
SCDA_API_URL=http://staging.example.com:8000 pytest tests/test_scenario_validation.py -v
```

---

## Interpreting Results

### PASS

The system returned a risk level that meets or exceeds the expected level for known danger zones, or correctly returned LOW/MEDIUM for safe baselines.

### FAIL

One of two conditions:
1. **Known danger zone returned LOW** — The system is under-reporting risk. This is the most critical failure type and indicates a calibration bug.
2. **Safe baseline returned HIGH/CRITICAL** — The system is over-sensitizing and may cause alert fatigue.

### Report File

After each run, a summary report is written to:
```
tests/results/scenario_report.txt
```

Format:
```
[PASS] SHP-WX-001 | WEATHER_STORM_CAPE | expected=HIGH actual=HIGH
[FAIL] SHP-SN-006 | SANCTIONS_OFAC_VESSEL | expected=CRITICAL actual=LOW | Vessel IMO on OFAC SDN list
```

---

## How to Add New Scenarios

### Step 1: Choose the Right CSV

Pick the CSV that matches the risk module you want to test.

### Step 2: Add a Row

Follow the existing column format. Key fields:
- **test_scenario_tag**: Unique identifier (use format `CATEGORY_DESCRIPTION`)
- **expected_risk_level**: The ground truth — what the system MUST return
- **expected_risk_reason / risk_justification**: Document WHY this is the expected level

### Step 3: Verify Real-World Basis

Every HIGH or CRITICAL scenario must be backed by real-world evidence:
- Storm corridors: cite historical weather data (Beaufort scale, wave heights)
- Sanctions: cite OFAC SDN list entries or UN resolutions
- Congestion: cite UNCTAD port performance data
- Tariffs: cite WTO/WITS tariff schedules or trade policy announcements

### Step 4: Run and Validate

```bash
pytest tests/test_scenario_validation.py -k "YOUR_NEW_TAG" -v
```

---

## Which Scenarios Require Live API Keys vs Mock Data

| Scenario Type | Live API Required | Mock-Compatible |
|---------------|:-----------------:|:---------------:|
| Weather (Open-Meteo) | ✅ | ✅ (historical data) |
| Sanctions (OFAC SDN) | ✅ (for real-time list) | ✅ (cached list) |
| Port Congestion | ✅ (live data) | ✅ (UNCTAD baseline) |
| Tariff Rates | ✅ (WTO/WITS) | ✅ (known rates) |
| Vessel Registry (Equasis) | ✅ (live lookup) | ✅ (cached records) |
| Route Distance (Searoute) | ❌ (local calculation) | ✅ |
| Risk Scoring Integration | ❌ (internal logic) | ✅ |

**For CI/CD pipelines**: Use `use_live_intelligence=False` in the shipment risk payload to test scoring logic without external API dependencies. The integration tests (`test_risk_scoring_integration.csv`) are designed to work without live APIs.

---

## Scenario Design Philosophy

1. **Every row has a real-world basis** — No synthetic or arbitrary risk levels
2. **Baselines are included** — Each category has at least one LOW/safe scenario to prevent over-sensitization
3. **Combined scenarios test aggregation** — Row 15 (COMBINED_ALL_RISKS) validates that multiple risk factors compound correctly
4. **Geopolitical scenarios reflect current threats** — Red Sea/Houthi corridor, Strait of Hormuz tensions
5. **Tariff scenarios use actual policy** — Section 301, USMCA, anti-dumping duties with real HS codes
