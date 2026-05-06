"""Shipment feature extraction and quantitative risk scoring."""
from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Any

from app.ingestion.trade_monitor import fetch_trade_policy_events
from app.ingestion.vessel_tracker import (
    VesselTrackerClient,
    normalize_vessel_event,
    vessel_from_shipment,
)
from app.ingestion.weather_monitor import (
    fetch_open_meteo_marine_weather,
    fetch_weather_events,
    normalize_marine_weather_event,
)
from app.ingestion.worldmonitor import (
    fetch_global_disruption_news,
    fetch_supply_chain_news,
    normalize_news_event,
)
from app.models.schemas import ShipmentInput

logger = logging.getLogger(__name__)

MODEL_PATH = Path("models/risk_model.pkl")
MODEL_VERSION = "shipment-risk-v2"

FEATURE_NAMES = [
    "lead_time_days",
    "inventory_pressure",
    "supplier_delay_count",
    "priority_score",
    "declared_value_score",
    "weather_severity_score",
    "trade_severity_score",
    "news_severity_score",
    "vessel_status_score",
    "marine_weather_score",
    "route_progress_score",
    "route_signal_count",
    "is_air",
    "is_sea",
    "is_multimodal",
    # --- V2 engineered features ---
    "max_external_severity",
    "external_signal_diversity",
    "inventory_x_delays",
    "urgency_pressure",
    "marine_compound",
    "geopolitical_compound",
    "early_route_exposure",
    "core_pressure",
]

SEVERITY_SCORE = {
    "low": 1.5,
    "medium": 4.0,
    "high": 7.0,
    "critical": 9.0,
}

PRIORITY_SCORE = {
    "low": 1.0,
    "normal": 3.0,
    "high": 6.0,
    "urgent": 8.0,
}

WEATHER_ROUTE_PROXIMITY_KM = 750.0
MARINE_ROUTE_PROXIMITY_KM = 250.0

ROUTE_NODE_PROFILES: dict[str, dict[str, Any]] = {
    "busan": {
        "latitude": 35.1796,
        "longitude": 129.0756,
        "country": "south korea",
        "aliases": ["korea", "east asia", "pacific"],
    },
    "dubai": {
        "latitude": 25.2048,
        "longitude": 55.2708,
        "country": "united arab emirates",
        "aliases": ["uae", "persian gulf", "arabian gulf", "middle east", "gulf of oman", "hormuz"],
    },
    "gibraltar": {
        "latitude": 36.1408,
        "longitude": -5.3536,
        "country": "gibraltar",
        "aliases": ["strait of gibraltar", "mediterranean", "atlantic"],
    },
    "hamburg": {
        "latitude": 53.5511,
        "longitude": 9.9937,
        "country": "germany",
        "aliases": ["europe", "north sea"],
    },
    "hormuz": {
        "latitude": 26.5667,
        "longitude": 56.25,
        "country": "oman",
        "aliases": ["strait of hormuz", "iran", "qatar", "persian gulf", "arabian gulf", "gulf of oman", "middle east"],
    },
    "los angeles": {
        "latitude": 33.7405,
        "longitude": -118.2775,
        "country": "united states",
        "aliases": ["usa", "us west coast", "pacific"],
    },
    "mundra": {
        "latitude": 22.8395,
        "longitude": 69.7219,
        "country": "india",
        "aliases": [
            "gujarat",
            "mumbai",
            "arabian sea",
            "indian ocean",
            "gulf of oman",
            "hormuz",
            "middle east",
        ],
    },
    "mumbai": {
        "latitude": 19.076,
        "longitude": 72.8777,
        "country": "india",
        "aliases": ["maharashtra", "gujarat", "arabian sea", "indian ocean", "mundra"],
    },
    "newark": {
        "latitude": 40.7357,
        "longitude": -74.1724,
        "country": "united states",
        "aliases": ["usa", "us east coast", "new york", "new jersey", "north atlantic"],
    },
    "ningbo": {
        "latitude": 29.8683,
        "longitude": 121.544,
        "country": "china",
        "aliases": ["east china", "east asia"],
    },
    "north atlantic": {
        "latitude": 42.0,
        "longitude": -35.0,
        "country": "",
        "aliases": ["atlantic", "transatlantic", "us east coast", "europe"],
    },
    "pacific ocean": {
        "latitude": 28.0,
        "longitude": -160.0,
        "country": "",
        "aliases": ["pacific", "transpacific"],
    },
    "ras tanura": {
        "latitude": 26.6427,
        "longitude": 50.1594,
        "country": "saudi arabia",
        "aliases": ["persian gulf", "arabian gulf", "gulf of oman", "hormuz", "qatar", "iran", "middle east"],
    },
    "rotterdam": {
        "latitude": 51.9244,
        "longitude": 4.4777,
        "country": "netherlands",
        "aliases": ["europe", "north sea"],
    },
    "shanghai": {
        "latitude": 31.2304,
        "longitude": 121.4737,
        "country": "china",
        "aliases": ["east china", "east asia"],
    },
    "singapore": {
        "latitude": 1.3521,
        "longitude": 103.8198,
        "country": "singapore",
        "aliases": ["malacca", "strait of malacca", "southeast asia"],
    },
    "suez canal": {
        "latitude": 30.5852,
        "longitude": 32.2654,
        "country": "egypt",
        "aliases": ["suez", "red sea", "middle east", "mediterranean"],
    },
    "yantian": {
        "latitude": 22.5565,
        "longitude": 114.2366,
        "country": "china",
        "aliases": ["shenzhen", "south china", "east asia"],
    },
}

GLOBAL_TRADE_POLICY_TERMS = {
    "anti dumping",
    "anti-dumping",
    "border closed",
    "customs delay",
    "customs",
    "embargo",
    "export ban",
    "import restriction",
    "quota",
    "sanctions",
    "tariff",
    "trade restriction",
    "wto",
    "unctad",
    "un rules",
}

GLOBAL_NEWS_PRESSURE_TERMS = {
    "blockade",
    "border closure",
    "gas disruption",
    "logistics disruption",
    "port closure",
    "port congestion",
    "port strike",
    "sanctions",
    "shipping disruption",
    "supply chain disruption",
    "trade war",
    "vessel backlog",
    "war",
}

NEWS_SEVERITY_KEYWORDS = {
    "critical": ["blockade", "embargo", "border closed", "port closed", "war"],
    "high": ["sanctions", "trade war", "gas disruption", "shipping disruption", "port congestion", "vessel backlog"],
    "medium": ["supply chain disruption", "customs", "shortage", "strike", "tariff"],
}


class ShipmentRiskService:
    """Score shipment risk using an XGBoost model when available."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
            cls._instance._model_loaded = False
        return cls._instance

    def score_shipment(
        self,
        shipment: ShipmentInput,
        intelligence_events: list[dict[str, Any]] | None = None,
        use_live_intelligence: bool = True,
    ) -> dict[str, Any]:
        """Score a shipment and return model-ready features plus risk score."""
        events = list(intelligence_events or [])
        if use_live_intelligence:
            events.extend(self._fetch_live_intelligence(shipment))
        events = ensure_submitted_vessel_event(shipment, events)

        features, signals, evidence_events = extract_shipment_features(shipment, events)
        context_events = build_context_events(events, evidence_events)
        model = self._load_model()

        if model is not None:
            score = float(model.predict([[features[name] for name in FEATURE_NAMES]])[0])
            scoring_method = "xgboost_model"
        else:
            score = heuristic_risk_score(features)
            scoring_method = "heuristic_until_xgboost_model_is_trained"

        score = apply_contextual_adjustments(features, score)
        score = max(0.0, min(10.0, round(score, 2)))

        result = {
            "shipment_id": shipment.shipment_id,
            "risk_score": score,
            "risk_level": score_to_level(score),
            "scoring_method": scoring_method,
            "model_version": MODEL_VERSION,
            "features": features,
            "signals": signals,
            "evidence_events": evidence_events,
            "context_events": context_events,
        }

        # Send SES email alert for high/critical shipment risks
        if score >= 5.0:
            self._send_shipment_risk_email(shipment, result)

        return result

    def _send_shipment_risk_email(self, shipment: ShipmentInput, result: dict[str, Any]) -> None:
        """Send SES email notification for high/critical shipment risk scores."""
        try:
            from app.services.email_service import EmailService

            email_service = EmailService()
            risk_level = result["risk_level"]
            score = result["risk_score"]

            # Map to SES severity for routing
            ses_severity = "critical" if score >= 8.0 else "high"

            headline = (
                f"Shipment {shipment.shipment_id} — Risk Score {score}/10 ({risk_level.upper()})"
            )
            recommendations = [
                f"Route: {shipment.origin} → {shipment.destination}",
                f"Material: {shipment.material}",
                f"Supplier: {shipment.supplier}",
            ]
            if result.get("signals"):
                recommendations.append(f"Top signal: {result['signals'][0]}")

            email_result = email_service.send_routed_alert(
                risk_severity=ses_severity,
                risk_headline=headline,
                supplier=shipment.supplier,
                disruption_type="shipping_delay",
                recommendations=recommendations,
            )
            if email_result.success:
                logger.info(
                    "SES shipment risk alert sent: score=%.1f, recipients=%s",
                    score, email_result.recipients_notified,
                )
            else:
                logger.warning("SES shipment risk alert failed: %s", email_result.error)
        except Exception as e:
            logger.error("Shipment risk email notification failed: %s", e)

    def _fetch_live_intelligence(self, shipment: ShipmentInput) -> list[dict[str, Any]]:
        """Fetch all live intelligence sources in parallel for faster response."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        events: list[dict[str, Any]] = []

        def _vessel():
            return self._fetch_vessel_intelligence(shipment)

        def _flight():
            return self._fetch_flight_intelligence(shipment)

        def _weather():
            return fetch_weather_events(limit=10)

        def _trade():
            return fetch_trade_policy_events(limit=15)

        def _news():
            return fetch_news_context_events(limit=8)

        tasks = {
            "vessel": _vessel,
            "flight": _flight,
            "weather": _weather,
            "trade": _trade,
            "news": _news,
        }

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result(timeout=20)
                    if result:
                        events.extend(result)
                except Exception as exc:
                    logger.warning("Live %s intelligence unavailable: %s", name, exc)

        return events

    def _fetch_vessel_intelligence(self, shipment: ShipmentInput) -> list[dict[str, Any]]:
        if shipment.transport_mode.lower().strip() != "sea":
            return []

        events: list[dict[str, Any]] = []
        vessel = vessel_from_shipment(shipment)
        if vessel is None and shipment.imo_number:
            vessel = VesselTrackerClient().get_vessel_by_imo(shipment.imo_number)

        if not vessel:
            # Don't warn if we simply don't have IMO — MMSI-only is normal
            if shipment.imo_number:
                logger.warning("No vessel telemetry found for shipment %s", shipment.shipment_id)
            return events

        events.append(normalize_vessel_event(vessel))

        latitude = vessel.get("latitude")
        longitude = vessel.get("longitude")
        if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
            try:
                marine_payload = fetch_open_meteo_marine_weather(latitude, longitude)
                marine_event = normalize_marine_weather_event(vessel, marine_payload)
                if marine_event:
                    events.append(marine_event)
            except Exception as exc:
                logger.warning("Marine weather fetch failed for IMO %s: %s", shipment.imo_number, exc)

        return events

    def _fetch_flight_intelligence(self, shipment: ShipmentInput) -> list[dict[str, Any]]:
        """Fetch real-time flight position from OpenSky Network for air shipments."""
        if shipment.transport_mode.lower().strip() != "air":
            return []

        from app.ingestion.flight_tracker import (
            FlightTrackerClient,
            flight_from_shipment,
            normalize_flight_event,
        )

        events: list[dict[str, Any]] = []
        flight = flight_from_shipment(shipment)
        if flight is None and shipment.flight_callsign:
            flight = FlightTrackerClient().get_flight_by_callsign(shipment.flight_callsign)
        elif flight is None and shipment.flight_icao24:
            flight = FlightTrackerClient().get_flight_by_icao24(shipment.flight_icao24)

        if not flight:
            logger.warning("No flight telemetry found for shipment %s", shipment.shipment_id)
            return events

        events.append(normalize_flight_event(flight))
        return events

    def _load_model(self) -> Any | None:
        if self._model_loaded and self._model is None and MODEL_PATH.exists():
            self._model_loaded = False

        if self._model_loaded:
            return self._model

        self._model_loaded = True
        if not MODEL_PATH.exists():
            logger.info("No trained XGBoost model found at %s", MODEL_PATH)
            return None

        try:
            import joblib

            self._model = joblib.load(MODEL_PATH)
            logger.info("Loaded shipment risk model from %s", MODEL_PATH)
        except Exception as exc:
            logger.warning("Failed to load shipment risk model: %s", exc)
            self._model = None

        return self._model


def extract_shipment_features(
    shipment: ShipmentInput,
    intelligence_events: list[dict[str, Any]],
) -> tuple[dict[str, float], list[str], list[dict[str, Any]]]:
    """Turn a shipment and intelligence events into numeric model features."""
    route_terms = build_route_terms(shipment)
    route_profile = build_route_profile(shipment)
    matched_events = [event for event in intelligence_events if event_matches_route(event, route_terms, route_profile)]
    signals = build_signals(matched_events)
    evidence_events = build_evidence_events(matched_events)

    weather_score = max_event_score(matched_events, source_contains="weather_monitor")
    marine_weather_score = max_event_score(matched_events, source_contains="marine_weather")
    trade_score = max_event_score(matched_events, source_contains="trade")
    news_score = max_event_score(matched_events, source_contains="news")
    vessel_score = max_event_score(matched_events, source_contains="vessel")
    route_progress_score = max_route_progress_score(matched_events)

    mode = shipment.transport_mode.lower().strip()
    inventory_pressure = inventory_pressure_score(shipment.inventory_days_cover)

    features = {
        "lead_time_days": float(max(shipment.lead_time_days, 0.0)),
        "inventory_pressure": inventory_pressure,
        "supplier_delay_count": float(max(shipment.supplier_delay_count, 0)),
        "priority_score": priority_score_value(shipment.priority),
        "declared_value_score": declared_value_score(shipment.declared_value_usd),
        "weather_severity_score": weather_score,
        "trade_severity_score": trade_score,
        "news_severity_score": news_score,
        "vessel_status_score": vessel_score,
        "marine_weather_score": marine_weather_score,
        "route_progress_score": route_progress_score,
        "route_signal_count": float(min(len(matched_events), 5)),
        "is_air": 1.0 if mode == "air" else 0.0,
        "is_sea": 1.0 if mode == "sea" else 0.0,
        "is_multimodal": 1.0 if mode == "multimodal" else 0.0,
    }

    # --- V2 engineered interaction features ---
    ext_scores = [weather_score, marine_weather_score, trade_score, news_score]
    features["max_external_severity"] = max(ext_scores)
    features["external_signal_diversity"] = float(sum(1 for s in ext_scores if s >= 4.0))

    inv_norm = inventory_pressure / 10.0
    delay_norm = min(float(shipment.supplier_delay_count) / 5.0, 1.0)
    features["inventory_x_delays"] = round(inv_norm * delay_norm * 10.0, 2)

    pri_norm = priority_score_value(shipment.priority) / 10.0
    features["urgency_pressure"] = round(pri_norm * inv_norm * 10.0, 2)

    features["marine_compound"] = round(
        (marine_weather_score / 10.0) * (vessel_score / 10.0) * 10.0, 2
    ) if marine_weather_score > 0 and vessel_score > 0 else 0.0

    features["geopolitical_compound"] = round(
        (trade_score / 10.0) * (news_score / 10.0) * 10.0, 2
    ) if trade_score > 0 and news_score > 0 else 0.0

    features["early_route_exposure"] = round(
        (route_progress_score / 10.0) * (features["max_external_severity"] / 10.0) * 10.0, 2
    )

    features["core_pressure"] = round(
        min(features["lead_time_days"] / 45.0, 1.0) * 1.0
        + inv_norm * 2.2
        + delay_norm * 1.2
        + pri_norm * 1.0
        + min(features["declared_value_score"] / 10.0, 1.0) * 0.5
        + min(vessel_score / 10.0, 1.0) * 1.2,
        2,
    )

    return features, signals, evidence_events


def ensure_submitted_vessel_event(
    shipment: ShipmentInput,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Always include vessel telemetry supplied with the shipment payload."""
    if shipment.transport_mode.lower().strip() != "sea":
        return events

    already_has_vessel = any(str(event.get("source", "")).lower() == "vessel_tracker" for event in events)
    if already_has_vessel:
        return events

    vessel = vessel_from_shipment(shipment)
    if vessel:
        return [normalize_vessel_event(vessel), *events]

    return events


def build_route_terms(shipment: ShipmentInput) -> set[str]:
    """Build searchable location/material terms for event matching."""
    route_profile = build_route_profile(shipment)
    values = [
        shipment.origin,
        shipment.destination,
        shipment.material,
        shipment.imo_number,
        shipment.mmsi,
        *shipment.route_nodes,
        *route_profile["countries"],
        *route_profile["aliases"],
    ]
    return {
        normalized
        for value in values
        for normalized in [normalize_term(value)]
        if normalized
    }


def build_route_profile(shipment: ShipmentInput) -> dict[str, Any]:
    """Build known geography and route-risk aliases for shipment matching."""
    node_values = [shipment.origin, shipment.destination, *shipment.route_nodes]
    coordinates: list[tuple[float, float]] = []
    countries: set[str] = set()
    aliases: set[str] = set()

    for value in node_values:
        normalized = normalize_term(value)
        profile = ROUTE_NODE_PROFILES.get(normalized)
        if not profile:
            continue

        latitude = profile.get("latitude")
        longitude = profile.get("longitude")
        if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
            coordinates.append((float(latitude), float(longitude)))

        country = normalize_term(profile.get("country", ""))
        if country:
            countries.add(country)
        aliases.update(normalize_term(alias) for alias in profile.get("aliases", []) if normalize_term(alias))

    if shipment.vessel_latitude is not None and shipment.vessel_longitude is not None:
        coordinates.append((float(shipment.vessel_latitude), float(shipment.vessel_longitude)))

    return {
        "coordinates": coordinates,
        "countries": countries,
        "aliases": aliases,
        "is_international": len(countries) >= 2 or normalize_term(shipment.origin) != normalize_term(shipment.destination),
        "is_sea": shipment.transport_mode.lower().strip() == "sea",
    }


def event_matches_route(
    event: dict[str, Any],
    route_terms: set[str],
    route_profile: dict[str, Any] | None = None,
) -> bool:
    """Check whether an intelligence event overlaps the shipment route/material."""
    if not route_terms:
        return False

    metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
    haystack = normalize_term(
        " ".join(
            [
                str(event.get("text", "")),
                str(event.get("source", "")),
                str(metadata.get("title", "")),
                str(metadata.get("summary", "")),
                str(metadata.get("location", "")),
                str(metadata.get("country", "")),
                str(metadata.get("imo_number", "")),
                str(metadata.get("vessel_name", "")),
                str(metadata.get("origin", "")),
                str(metadata.get("destination", "")),
            ]
        )
    )

    if any(term in haystack for term in route_terms if len(term) >= 3):
        return True

    if not route_profile:
        return False

    source = str(event.get("source", "")).lower()
    if "weather" in source and event_matches_weather_route(event, route_profile):
        return True
    if "trade" in source and event_matches_trade_route(haystack, route_profile):
        return True
    if "news" in source and event_matches_news_route(haystack, route_profile):
        return True

    return False


def event_matches_weather_route(event: dict[str, Any], route_profile: dict[str, Any]) -> bool:
    """Match weather/marine events by route country or coordinate proximity."""
    metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
    source = str(event.get("source", "")).lower()
    event_country = normalize_term(metadata.get("country", ""))
    if event_country and event_country in route_profile["countries"]:
        return True

    latitude = _float_or_none(metadata.get("latitude"))
    longitude = _float_or_none(metadata.get("longitude"))
    if latitude is None or longitude is None:
        return False

    threshold = MARINE_ROUTE_PROXIMITY_KM if "marine" in source else WEATHER_ROUTE_PROXIMITY_KM
    return any(
        haversine_km(latitude, longitude, route_latitude, route_longitude) <= threshold
        for route_latitude, route_longitude in route_profile["coordinates"]
    )


def event_matches_trade_route(haystack: str, route_profile: dict[str, Any]) -> bool:
    """Treat official trade signals as route-relevant for international flows."""
    if any(term in haystack for term in route_profile["countries"] | route_profile["aliases"] if len(term) >= 3):
        return True
    return bool(route_profile["is_international"] and any(term in haystack for term in GLOBAL_TRADE_POLICY_TERMS))


def event_matches_news_route(haystack: str, route_profile: dict[str, Any]) -> bool:
    """Match high-impact global or regional news to exposed routes."""
    if any(term in haystack for term in route_profile["countries"] | route_profile["aliases"] if len(term) >= 3):
        return True
    if route_profile["is_sea"] and any(term in haystack for term in GLOBAL_NEWS_PRESSURE_TERMS):
        return True
    return False


def max_event_score(events: list[dict[str, Any]], source_contains: str) -> float:
    """Return the strongest severity score for matching event source type."""
    scores = []
    for event in events:
        source = str(event.get("source", "")).lower()
        if source_contains == "weather_monitor":
            if source != "weather_monitor":
                continue
        elif source_contains not in source:
            continue
        severity = infer_event_severity(event)
        scores.append(SEVERITY_SCORE.get(severity, 4.0))
    return max(scores, default=0.0)


def infer_event_severity(event: dict[str, Any]) -> str:
    """Return event severity, inferring it for RSS news that lacks severity metadata."""
    metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
    severity = str(metadata.get("severity", "")).lower()
    if severity in SEVERITY_SCORE:
        return severity

    haystack = normalize_term(
        " ".join(
            [
                str(event.get("text", "")),
                str(metadata.get("title", "")),
                str(metadata.get("summary", "")),
            ]
        )
    )
    for inferred_severity, keywords in NEWS_SEVERITY_KEYWORDS.items():
        if any(normalize_term(keyword) in haystack for keyword in keywords):
            return inferred_severity
    return "medium"


def max_route_progress_score(events: list[dict[str, Any]]) -> float:
    """Score early-route exposure higher than near-arrival exposure."""
    scores = []
    for event in events:
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        progress = metadata.get("progress_percent")
        if progress is None:
            continue
        try:
            progress_float = float(progress)
        except (TypeError, ValueError):
            continue
        if progress_float < 25:
            scores.append(8.0)
        elif progress_float < 60:
            scores.append(5.0)
        else:
            scores.append(2.0)
    return max(scores, default=0.0)


def build_signals(events: list[dict[str, Any]]) -> list[str]:
    """Build readable signals for API/debug output."""
    signals = []
    for event in events[:6]:
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        title = metadata.get("title") or str(event.get("text", ""))[:100]
        source = event.get("source", "intelligence")
        signals.append(f"{source}: {title}")
    return signals


def build_evidence_events(events: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    """Build structured evidence for detail pages and model explainability."""
    evidence = []
    for event in events[:limit]:
        metadata = event.get("metadata", {}) if isinstance(event.get("metadata"), dict) else {}
        evidence.append(
            {
                "source": event.get("source", "intelligence"),
                "title": metadata.get("title") or str(event.get("text", ""))[:100],
                "summary": metadata.get("summary") or event.get("text", ""),
                "severity": infer_event_severity(event),
                "event_time": event.get("event_time", ""),
                "metadata": {
                    key: value
                    for key, value in metadata.items()
                    if key
                    in {
                        "location",
                        "country",
                        "latitude",
                        "longitude",
                        "weather_code",
                        "precipitation",
                        "wind_speed_10m",
                        "wind_gusts_10m",
                        "wave_height",
                        "swell_wave_height",
                        "wind_wave_height",
                        "ocean_current_velocity",
                        "imo_number",
                        "vessel_name",
                        "status",
                        "speed_knots",
                        "progress_percent",
                        "origin",
                        "destination",
                        "link",
                        "published",
                    }
                },
            }
        )
    return evidence


def build_context_events(
    events: list[dict[str, Any]],
    matched_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build non-scoring context events for demo visibility.

    These are live signals the system checked, whether or not they matched the
    route strongly enough to become scoring evidence.
    """
    matched_titles = {normalize_term(event.get("title", "")) for event in matched_evidence}
    context = []
    for event in build_evidence_events(events, limit=len(events))[:24]:
        source = str(event.get("source", "")).lower()
        if not any(term in source for term in ["weather", "marine", "trade", "news"]):
            continue
        if normalize_term(event.get("title", "")) in matched_titles:
            continue
        context.append(event)
    return context[:12]


def fetch_news_context_events(limit: int = 8) -> list[dict[str, Any]]:
    """Fetch a small World Monitor news sample for visibility on the detail page."""
    events = []
    supply_items = fetch_supply_chain_news(limit=max(1, limit // 2))
    for idx, item in enumerate(supply_items):
        events.append(normalize_news_event(item, idx, "news_feed"))

    global_items = fetch_global_disruption_news(limit=max(1, limit - len(events)))
    for idx, item in enumerate(global_items):
        events.append(normalize_news_event(item, idx + len(events), "global_news"))

    return events[:limit]


def heuristic_risk_score(features: dict[str, float]) -> float:
    """Transparent fallback score until a real XGBoost model is trained."""
    score = 0.0
    score += min(features["lead_time_days"] / 45.0, 1.0) * 1.0
    score += min(features["inventory_pressure"] / 10.0, 1.0) * 2.2
    score += min(features["supplier_delay_count"] / 5.0, 1.0) * 1.2
    score += min(features["priority_score"] / 10.0, 1.0) * 1.0
    score += min(features["declared_value_score"] / 10.0, 1.0) * 0.5
    score += min(features["weather_severity_score"] / 10.0, 1.0) * 0.8
    score += min(features["trade_severity_score"] / 10.0, 1.0) * 1.1
    score += min(features["news_severity_score"] / 10.0, 1.0) * 0.5
    score += min(features["vessel_status_score"] / 10.0, 1.0) * 1.2
    score += min(features["marine_weather_score"] / 10.0, 1.0) * 0.8
    score += min(features["route_progress_score"] / 10.0, 1.0) * 0.5
    score += min(features["route_signal_count"] / 5.0, 1.0) * 0.8

    # V2 interaction features contribute directly
    score += min(features.get("inventory_x_delays", 0) / 10.0, 1.0) * 0.6
    score += min(features.get("urgency_pressure", 0) / 10.0, 1.0) * 0.4
    score += min(features.get("marine_compound", 0) / 10.0, 1.0) * 0.5
    score += min(features.get("geopolitical_compound", 0) / 10.0, 1.0) * 0.4
    score += min(features.get("early_route_exposure", 0) / 10.0, 1.0) * 0.3

    if features["is_air"]:
        score += 0.2
    if features["is_multimodal"]:
        score += 0.4

    return apply_context_guardrails(features, score)


def apply_contextual_adjustments(features: dict[str, float], score: float) -> float:
    """Let route-matched external signals amplify, without overruling shipment fundamentals."""
    external_strength = max(
        features["weather_severity_score"],
        features["marine_weather_score"],
        features["trade_severity_score"],
        features["news_severity_score"],
    )
    if external_strength <= 0:
        return score

    core_pressure = core_shipment_pressure(features)
    if core_pressure < 2.0:
        return apply_context_guardrails(features, score)

    external_mix = sum(
        1
        for name in [
            "weather_severity_score",
            "marine_weather_score",
            "trade_severity_score",
            "news_severity_score",
        ]
        if features[name] > 0
    )
    signal_density = min(features["route_signal_count"] / 5.0, 1.0)
    boost = min(2.0, (external_strength / 10.0) * 0.9 + external_mix * 0.18 + signal_density * 0.35)

    return apply_context_guardrails(features, score + boost)


def core_shipment_pressure(features: dict[str, float]) -> float:
    """Score only shipment-owned data, excluding external weather/news/trade context."""
    pressure = 0.0
    pressure += min(features["lead_time_days"] / 45.0, 1.0) * 1.0
    pressure += min(features["inventory_pressure"] / 10.0, 1.0) * 2.2
    pressure += min(features["supplier_delay_count"] / 5.0, 1.0) * 1.2
    pressure += min(features["priority_score"] / 10.0, 1.0) * 1.0
    pressure += min(features["declared_value_score"] / 10.0, 1.0) * 0.5
    pressure += min(features["vessel_status_score"] / 10.0, 1.0) * 1.2
    pressure += min(features["route_progress_score"] / 10.0, 1.0) * 0.5
    return pressure


def apply_context_guardrails(features: dict[str, float], score: float) -> float:
    """Keep external context from becoming the whole risk decision by itself.

    Weather, marine weather, trade, and news are treated as amplifiers. They can
    raise urgency when the shipment already has operational pressure, but they
    should not turn a healthy shipment into a high/critical risk on their own.
    """
    external_context = max(
        features["weather_severity_score"],
        features["marine_weather_score"],
        features["trade_severity_score"],
        features["news_severity_score"],
    )
    if external_context <= 0:
        return score

    core_pressure = core_shipment_pressure(features)
    external_signal_count = sum(
        1
        for name in [
            "weather_severity_score",
            "marine_weather_score",
            "trade_severity_score",
            "news_severity_score",
        ]
        if features[name] > 0
    )
    if core_pressure < 2.0:
        return min(score, 3.8)
    if core_pressure < 3.5:
        if external_context >= 7 and external_signal_count >= 2:
            return min(score, 6.2)
        return min(score, 5.2)
    if core_pressure < 5.0:
        if external_context >= 7 and external_signal_count >= 2:
            return min(score, 8.4)
        return min(score, 7.2)
    return score


def score_to_level(score: float) -> str:
    """Convert 0-10 score into dashboard-friendly level."""
    if score >= 8:
        return "critical"
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def inventory_pressure_score(days_of_cover: float) -> float:
    """Higher score means lower inventory buffer."""
    if days_of_cover <= 0:
        return 10.0
    if days_of_cover >= 30:
        return 0.0
    return round((30.0 - days_of_cover) / 3.0, 2)


def declared_value_score(value_usd: float) -> float:
    """Scale shipment value into a bounded risk exposure feature."""
    if value_usd <= 0:
        return 0.0
    if value_usd >= 1_000_000:
        return 10.0
    return round(value_usd / 100_000.0, 2)


def priority_score_value(priority: Any) -> float:
    """Map buyer priority input to a 0-10 model feature.

    Supports both the old labels and the buyer scale:
    0 = low, 1 = normal, 2 = high, 3 = express/critical.
    """
    if isinstance(priority, (int, float)) or str(priority).strip().isdigit():
        value = max(0.0, min(3.0, float(priority)))
        return round((value / 3.0) * 10.0, 2)

    return PRIORITY_SCORE.get(str(priority).lower().strip(), 3.0)


def normalize_term(value: Any) -> str:
    """Normalize text for coarse matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).lower())).strip()


def haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Return great-circle distance between two coordinates."""
    radius_km = 6371.0
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)

    haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(haversine))


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
