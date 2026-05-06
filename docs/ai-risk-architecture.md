# AI Risk Architecture

This project uses a hybrid AI architecture:

```text
Dashboard / API
    -> Strands agent orchestration
    -> XGBoost quantitative scoring
    -> Bedrock qualitative reasoning and mitigation
    -> JSON response for dashboard
```

## Component Roles

### Strands

Strands is the controller. It decides which tools to call and in what order.

Planned tools:

- `fetch_world_intelligence`: news, weather, and trade-policy signals.
- `track_vessel_by_imo`: vessel telemetry for sea shipments.
- `score_risk`: XGBoost risk score from structured shipment features.
- `reason_with_bedrock`: explanation, mitigation, and routing.
- `validate_response`: JSON schema and quality guardrails.

### XGBoost

XGBoost should produce the numeric score:

```json
{
  "risk_score": 8.4
}
```

It should use structured features such as:

- Supplier region risk
- Lead time
- Inventory coverage
- Severe weather near route nodes
- Vessel status and live coordinates from IMO lookup
- Marine weather at the vessel's live position
- Trade-policy signal severity
- News disruption severity
- Port or airport exposure
- Historical supplier delay count

### Bedrock

Bedrock should explain the score and generate mitigation:

```json
{
  "risk_level": "Critical",
  "reason": "Severe weather near Mundra and a customs delay signal increase risk for the active shipment.",
  "actions": [
    "Check alternate port routing",
    "Increase buffer stock",
    "Notify procurement and logistics teams"
  ]
}
```

## Live Intelligence Feeds

Current feeds added to ingestion:

- Global supply-chain news from RSS feeds.
- Weather intelligence from Open-Meteo for major logistics nodes.
- Trade-policy intelligence from WTO and public trade-policy feeds.

These feeds are normalized into the same event format used by the existing ingestion pipeline, so the engine can cross-reference them with active supplier emails, inventory, and future shipment records.

## Step Plan

1. Live external intelligence feeds. Done.
2. Shipment schema and feature extraction. Done.
3. XGBoost training and local model serving. In progress.
4. Bedrock response formatting and guardrails. Done.
5. Strands agent tools that orchestrate the full workflow. Done.

## Shipment Risk Endpoint

The quantitative scoring endpoint is:

```text
POST /shipments/risk-score
```

Example request:

```json
{
  "shipment": {
    "shipment_id": "SHP-1001",
    "supplier": "Nova Plastics",
    "origin": "Mundra",
    "destination": "Mumbai",
    "route_nodes": ["Mundra", "Mumbai"],
    "imo_number": "9811000",
    "transport_mode": "sea",
    "material": "ABS Resin",
    "lead_time_days": 14,
    "inventory_days_cover": 2,
    "supplier_delay_count": 3,
    "priority": "urgent",
    "declared_value_usd": 250000
  },
  "use_live_intelligence": true
}
```

If `models/risk_model.pkl` exists, the endpoint uses that model. Otherwise it returns a transparent heuristic score using the same feature vector, so the API remains usable before training data is ready.

## Vessel Tracking

Sea shipments can include an `imo_number`. The backend resolves it through:
Sea shipments should send live vessel telemetry from the vessel tracker when
available:

```json
{
  "imo_number": "9811000",
  "vessel_latitude": 28.94,
  "vessel_longitude": 49.23,
  "vessel_status": "UNDERWAY",
  "vessel_speed_knots": 13.4,
  "vessel_progress_percent": 62
}
```

No API key is required for that path. The backend uses the submitted live
coordinates to fetch marine weather.

The IMO lookup endpoint remains available for fallback/demo use:

```text
GET /vessels/{imo_number}
```

If `VESSEL_TRACKER_API_URL` is configured, the backend can call that provider
with `?imo=<number>`. If it is not configured, it uses the demo vessel records
from `vessel-tracker.html`.

When an IMO is present, shipment scoring adds:

- `vessel_status_score`
- `marine_weather_score`
- `route_progress_score`

## Shipment Advice Endpoint

The final decision endpoint is:

```text
POST /shipments/risk-advice
```

It runs:

```text
shipment input
  -> XGBoost/heuristic score
  -> Bedrock reasoning
  -> JSON guardrails
  -> final advice response
```

If Bedrock is not configured or returns invalid JSON, the service returns a deterministic fallback with the same response schema.

## Strands Agent Endpoint

The Strands orchestration endpoint is:

```text
POST /agents/strands/shipment-risk
```

It exposes the `SupplyChainRiskAgent` workflow:

```text
track_vessel_by_imo
  -> score_shipment_risk
  -> generate_shipment_advice
  -> validate_risk_response
```

When `strands-agents` is installed, the endpoint builds a real Strands `Agent`
with those tools and executes the tools through the agent registry. If the SDK
is not installed, it runs the same sequence locally and marks the response as
`local_mirror_of_strands_workflow`.

Strands tools are defined in:

```text
app/agents/supply_chain_agent.py
```
