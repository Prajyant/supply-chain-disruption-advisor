"""Compact, cache-backed live intelligence feed for the operations map."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.ingestion.worldmonitor import fetch_realtime_news

intelligence_router = APIRouter(prefix="/intelligence", tags=["live intelligence"])

_CACHE_TTL_SECONDS = 120
_cache: dict[str, Any] = {"expires_at": 0.0, "events": []}
_cache_lock = asyncio.Lock()


def _normalise_event(event: dict[str, Any]) -> dict[str, Any]:
    """Expose only the map-safe fields needed by the browser."""
    metadata = event.get("metadata") or {}
    return {
        "id": event.get("reference_id") or metadata.get("link") or event.get("event_time"),
        "source": event.get("source", "intelligence"),
        "title": metadata.get("title") or event.get("text", "Live intelligence update"),
        "summary": metadata.get("summary") or event.get("text", ""),
        "published_at": event.get("event_time") or metadata.get("published"),
        "url": metadata.get("link") or None,
        "severity": metadata.get("severity") or "info",
        "latitude": metadata.get("latitude"),
        "longitude": metadata.get("longitude"),
        "location": metadata.get("location"),
    }


async def _get_events() -> list[dict[str, Any]]:
    if _cache["events"] and time.monotonic() < _cache["expires_at"]:
        return _cache["events"]

    async with _cache_lock:
        if _cache["events"] and time.monotonic() < _cache["expires_at"]:
            return _cache["events"]
        raw_events = await asyncio.to_thread(fetch_realtime_news)
        _cache["events"] = [_normalise_event(event) for event in raw_events]
        _cache["expires_at"] = time.monotonic() + _CACHE_TTL_SECONDS
        return _cache["events"]


@intelligence_router.get("/live")
async def get_live_intelligence(limit: int = Query(12, ge=1, le=50)) -> dict[str, Any]:
    """Return current RSS, weather, and trade signals for the command map.

    The upstream feeds are refreshed at most once every two minutes across all
    users, preventing a map refresh from multiplying external requests.
    """
    events = await _get_events()
    return {
        "events": events[:limit],
        "count": min(len(events), limit),
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "cache_ttl_seconds": _CACHE_TTL_SECONDS,
    }
