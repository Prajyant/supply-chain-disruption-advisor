from app.models.schemas import ShipmentInput
from app.services.gemini_advice_service import classify_gemini_error
from app.services.shipment_risk_service import extract_shipment_features


def test_route_relevant_external_context_sets_scoring_features() -> None:
    shipment = ShipmentInput(
        shipment_id="SHP-1006",
        supplier="Meridian Chemicals",
        origin="Mundra",
        destination="Newark",
        route_nodes=["Mundra", "Suez Canal", "Gibraltar", "Newark"],
        vessel_name="MV GUJARAT TRADER",
        vessel_latitude=22.9,
        vessel_longitude=69.7,
        vessel_status="WAITING",
        vessel_speed_knots=0.6,
        vessel_progress_percent=12,
        transport_mode="sea",
        material="chemical feedstock",
        quantity=800,
        lead_time_days=18,
        inventory_days_cover=5,
        supplier_delay_count=2,
        priority=2,
        declared_value_usd=320000,
    )
    events = [
        {
            "source": "weather_monitor",
            "event_time": "2026-04-30T12:45",
            "text": "CRITICAL weather risk near Mumbai, India: thunderstorm.",
            "metadata": {
                "title": "Critical weather risk near Mumbai, India",
                "summary": "Thunderstorm near Mumbai may affect port, airport, road, or canal delays.",
                "severity": "critical",
                "location": "Mumbai",
                "country": "India",
                "latitude": 19.076,
                "longitude": 72.8777,
            },
        },
        {
            "source": "trade_policy_monitor",
            "event_time": "Tue, 28 Apr 2026 00:00:00 GMT",
            "text": "HIGH trade policy signal: WTO anti-dumping actions reviewed.",
            "metadata": {
                "title": "Members review notifications, anti-dumping actions",
                "summary": "WTO committee reviewed anti-dumping actions.",
                "severity": "high",
            },
        },
        {
            "source": "news_feed",
            "event_time": "Thu, 30 Apr 2026 08:48:08 GMT",
            "text": "Pakistan opens road trade routes into Iran amid Hormuz blockade.",
            "metadata": {
                "title": "Pakistan opens up road trade routes into Iran amid Hormuz blockade",
                "summary": "Regional trade disruption continues around the Strait of Hormuz.",
            },
        },
        {
            "source": "marine_weather_monitor",
            "event_time": "2026-04-30T12:45",
            "text": "HIGH marine weather risk near MV GUJARAT TRADER.",
            "metadata": {
                "title": "High marine weather risk near MV GUJARAT TRADER",
                "summary": "High marine weather risk near the active vessel.",
                "severity": "high",
                "vessel_name": "MV GUJARAT TRADER",
                "latitude": 22.91,
                "longitude": 69.72,
            },
        },
    ]

    features, signals, evidence_events = extract_shipment_features(shipment, events)

    assert features["weather_severity_score"] == 9.0
    assert features["trade_severity_score"] == 7.0
    assert features["news_severity_score"] == 9.0
    assert features["marine_weather_score"] == 7.0
    assert features["route_signal_count"] == 4.0
    assert len(signals) == 4
    assert {event["source"] for event in evidence_events} == {
        "weather_monitor",
        "trade_policy_monitor",
        "news_feed",
        "marine_weather_monitor",
    }


def test_classifies_gemini_quota_failure() -> None:
    error = Exception("429 RESOURCE_EXHAUSTED quota exceeded for generate_content")

    assert classify_gemini_error(error) == "gemini_quota_or_rate_limit"
