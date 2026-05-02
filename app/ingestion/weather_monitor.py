"""Weather intelligence feed for logistics disruption monitoring."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

LOGISTICS_WEATHER_WATCHLIST = [
    {"name": "Shanghai", "country": "China", "latitude": 31.2304, "longitude": 121.4737, "type": "port"},
    {"name": "Singapore", "country": "Singapore", "latitude": 1.3521, "longitude": 103.8198, "type": "port"},
    {"name": "Busan", "country": "South Korea", "latitude": 35.1796, "longitude": 129.0756, "type": "port"},
    {"name": "Mundra", "country": "India", "latitude": 22.8395, "longitude": 69.7219, "type": "port"},
    {"name": "Mumbai", "country": "India", "latitude": 19.0760, "longitude": 72.8777, "type": "port_airport"},
    {"name": "Dubai", "country": "United Arab Emirates", "latitude": 25.2048, "longitude": 55.2708, "type": "airport_port"},
    {"name": "Rotterdam", "country": "Netherlands", "latitude": 51.9244, "longitude": 4.4777, "type": "port"},
    {"name": "Suez Canal", "country": "Egypt", "latitude": 30.5852, "longitude": 32.2654, "type": "canal"},
    {"name": "Los Angeles", "country": "United States", "latitude": 33.7405, "longitude": -118.2775, "type": "port"},
    {"name": "Tokyo", "country": "Japan", "latitude": 35.6762, "longitude": 139.6503, "type": "port_airport"},
]

SEVERE_WEATHER_CODES = {
    65: "heavy rain",
    66: "freezing rain",
    67: "heavy freezing rain",
    75: "heavy snow",
    77: "snow grains",
    82: "violent rain showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}


def fetch_weather_events(limit: int = 20) -> list[dict[str, Any]]:
    """Fetch current weather for major logistics nodes and return normalized events."""
    events: list[dict[str, Any]] = []

    for idx, location in enumerate(LOGISTICS_WEATHER_WATCHLIST[:limit]):
        try:
            current = fetch_open_meteo_current_weather(
                latitude=location["latitude"],
                longitude=location["longitude"],
            )
            event = normalize_weather_event(location, current, idx)
            if event:
                events.append(event)
        except Exception as exc:
            logger.warning("Weather fetch failed for %s: %s", location["name"], exc)

    logger.info("Fetched %s weather intelligence events", len(events))
    return events


def fetch_open_meteo_current_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch current weather from Open-Meteo for one coordinate."""
    response = requests.get(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "precipitation",
                    "rain",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                ]
            ),
            "timezone": "UTC",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def fetch_open_meteo_marine_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch current marine weather from Open-Meteo for one coordinate."""
    response = requests.get(
        OPEN_METEO_MARINE_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                [
                    "wave_height",
                    "wave_direction",
                    "wave_period",
                    "wind_wave_height",
                    "swell_wave_height",
                    "ocean_current_velocity",
                    "ocean_current_direction",
                ]
            ),
            "timezone": "UTC",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def normalize_marine_weather_event(
    vessel: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Normalize marine weather near a vessel into the advisor event format."""
    current = payload.get("current", {}) or {}
    wave_height = _float_or_none(current.get("wave_height")) or 0.0
    wind_wave_height = _float_or_none(current.get("wind_wave_height")) or 0.0
    swell_wave_height = _float_or_none(current.get("swell_wave_height")) or 0.0
    ocean_current_velocity = _float_or_none(current.get("ocean_current_velocity")) or 0.0
    wave_period = _float_or_none(current.get("wave_period")) or 0.0

    severity = score_marine_weather_severity(
        wave_height=wave_height,
        wind_wave_height=wind_wave_height,
        swell_wave_height=swell_wave_height,
        ocean_current_velocity=ocean_current_velocity,
        wave_period=wave_period,
    )

    if severity == "low":
        return None

    vessel_name = vessel.get("name") or vessel.get("imo_number") or "vessel"
    text = (
        f"{severity.upper()} marine weather risk near {vessel_name}. "
        f"Wave height {wave_height:.1f} m, swell {swell_wave_height:.1f} m, "
        f"wind wave {wind_wave_height:.1f} m, current {ocean_current_velocity:.1f} km/h. "
        "Potential shipment impact: vessel delay, rerouting, cargo handling risk, or ETA uncertainty."
    )

    return {
        "source": "marine_weather_monitor",
        "reference_id": f"MARINE-{vessel.get('imo_number')}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "supplier": "Ocean Carrier",
        "event_time": current.get("time") or datetime.now(timezone.utc).isoformat(),
        "text": text,
        "metadata": {
            "title": f"{severity.title()} marine weather risk near {vessel_name}",
            "summary": text,
            "severity": severity,
            "imo_number": vessel.get("imo_number"),
            "vessel_name": vessel_name,
            "latitude": vessel.get("latitude"),
            "longitude": vessel.get("longitude"),
            "wave_height": wave_height,
            "wind_wave_height": wind_wave_height,
            "swell_wave_height": swell_wave_height,
            "ocean_current_velocity": ocean_current_velocity,
            "wave_period": wave_period,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def normalize_weather_event(
    location: dict[str, Any],
    payload: dict[str, Any],
    idx: int,
) -> dict[str, Any] | None:
    """Normalize Open-Meteo response into the advisor event format."""
    current = payload.get("current", {}) or {}
    weather_code = _int_or_none(current.get("weather_code"))
    precipitation = _float_or_none(current.get("precipitation")) or 0.0
    rain = _float_or_none(current.get("rain")) or 0.0
    wind_speed = _float_or_none(current.get("wind_speed_10m")) or 0.0
    wind_gusts = _float_or_none(current.get("wind_gusts_10m")) or 0.0
    temperature = _float_or_none(current.get("temperature_2m"))

    severity = score_weather_severity(
        weather_code=weather_code,
        precipitation=precipitation,
        rain=rain,
        wind_speed=wind_speed,
        wind_gusts=wind_gusts,
    )

    if severity == "low":
        return None

    weather_label = SEVERE_WEATHER_CODES.get(weather_code, "adverse weather")
    place = f"{location['name']}, {location['country']}"
    text = (
        f"{severity.upper()} weather risk near {place}: {weather_label}. "
        f"Wind {wind_speed:.1f} km/h, gusts {wind_gusts:.1f} km/h, "
        f"precipitation {precipitation:.1f} mm. "
        "Potential shipment impact: port, airport, road, or canal delays."
    )

    return {
        "source": "weather_monitor",
        "reference_id": f"WEATHER-{idx}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "supplier": "Global Logistics",
        "event_time": current.get("time") or datetime.now(timezone.utc).isoformat(),
        "text": text,
        "metadata": {
            "title": f"{severity.title()} weather risk near {place}",
            "summary": text,
            "location": location["name"],
            "country": location["country"],
            "node_type": location["type"],
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "severity": severity,
            "weather_code": weather_code,
            "temperature_2m": temperature,
            "precipitation": precipitation,
            "rain": rain,
            "wind_speed_10m": wind_speed,
            "wind_gusts_10m": wind_gusts,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def score_weather_severity(
    *,
    weather_code: int | None,
    precipitation: float,
    rain: float,
    wind_speed: float,
    wind_gusts: float,
) -> str:
    """Convert weather variables into coarse supply-chain risk severity."""
    if weather_code in {95, 96, 99} or wind_gusts >= 90 or precipitation >= 25 or rain >= 25:
        return "critical"
    if weather_code in SEVERE_WEATHER_CODES or wind_gusts >= 65 or precipitation >= 10 or rain >= 10:
        return "high"
    if wind_speed >= 45 or precipitation >= 5 or rain >= 5:
        return "medium"
    return "low"


def score_marine_weather_severity(
    *,
    wave_height: float,
    wind_wave_height: float,
    swell_wave_height: float,
    ocean_current_velocity: float,
    wave_period: float,
) -> str:
    """Convert marine variables into coarse sea-shipment risk severity."""
    worst_wave = max(wave_height, wind_wave_height, swell_wave_height)
    if worst_wave >= 8.0 or ocean_current_velocity >= 9.0:
        return "critical"
    if worst_wave >= 5.0 or ocean_current_velocity >= 6.0 or wave_period >= 14.0:
        return "high"
    if worst_wave >= 3.0 or ocean_current_velocity >= 4.0 or wave_period >= 10.0:
        return "medium"
    return "low"


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
