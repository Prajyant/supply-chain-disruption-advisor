"""
Vessel tracking API endpoints.

New endpoints for the vessel tracking system — uses existing auth decorators.
Integrates with the AIS engine, vessel database, and watchlist system.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.ingestion.ais.vessel_worker import get_vessel_worker

logger = logging.getLogger(__name__)

vessel_router = APIRouter(prefix="/vessels", tags=["vessels"])


# ==================== REQUEST/RESPONSE MODELS ====================


class VesselLinkRequest(BaseModel):
    """Request to link a vessel to a supplier/shipment."""
    linked_supplier: Optional[str] = None
    linked_shipment_id: Optional[str] = None


# ==================== HELPER ====================


def _get_engine():
    """Get the AIS engine from the vessel worker, initializing if needed."""
    worker = get_vessel_worker()
    if not worker.engine:
        worker.initialize()
    return worker.engine


# ==================== ENDPOINTS ====================


@vessel_router.get("/watchlist")
async def get_watchlist() -> dict:
    """Get all watched vessels with current status and identity.

    Returns fleet summary and list of all tracked vessels with their
    current position, status indicator, and linked supplier/shipment info.
    """
    engine = _get_engine()
    statuses = engine.get_all_vessel_statuses()
    fleet = engine.get_fleet_status()

    return {
        "fleet_summary": fleet,
        "vessels": statuses,
    }


@vessel_router.get("/fleet-status")
async def get_fleet_status() -> dict:
    """Get fleet status summary: active/stale/silent/danger-zone counts."""
    engine = _get_engine()
    return engine.get_fleet_status()


@vessel_router.get("/danger-zones")
async def get_danger_zones() -> dict:
    """Get danger zone definitions with vessels currently inside each zone."""
    engine = _get_engine()
    zones = engine.get_danger_zones()
    return {"zones": zones}


@vessel_router.get("/search")
async def search_vessels(q: str = Query(..., min_length=2)) -> dict:
    """Search for vessels by name (for IMO discovery).

    Searches the AIS provider's vessel database by partial name match.
    Useful for finding IMO numbers to add to the watchlist.
    """
    engine = _get_engine()
    results = await engine.provider.search_vessel(q)
    return {
        "query": q,
        "results": results[:20],
        "count": len(results),
    }


@vessel_router.get("/resolve/{imo}")
async def resolve_vessel(imo: str) -> dict:
    """Resolve an IMO number to full vessel identity.

    Checks local cache first, then queries the AIS provider.
    Caches the result for future lookups.
    """
    engine = _get_engine()

    # Check local identity cache
    identity = await asyncio.to_thread(engine.db.get_identity, imo)
    if identity:
        return {"source": "cache", "identity": identity}

    # Query provider
    vessel = await engine.provider.get_vessel_by_imo(imo)
    if vessel:
        await asyncio.to_thread(engine.db.upsert_identity, vessel)
        return {"source": "provider", "identity": vessel}

    raise HTTPException(status_code=404, detail=f"Could not resolve IMO {imo}")


@vessel_router.get("/{imo}/status")
async def get_vessel_status(imo: str) -> dict:
    """Get real-time vessel status including position, speed, and risk indicators."""
    engine = _get_engine()
    status = engine.get_vessel_status(imo)

    if not status:
        # Try fetching from provider directly
        vessel = await engine.provider.get_vessel_by_imo(imo)
        if vessel:
            return {**vessel, "status": "active", "source": "live_fetch"}
        raise HTTPException(status_code=404, detail=f"No data for IMO {imo}")

    return status


@vessel_router.get("/{imo}/track")
async def get_vessel_track(
    imo: str,
    hours: Optional[int] = Query(None, ge=1, le=720),
    days: Optional[int] = Query(None, ge=1, le=90),
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
) -> dict:
    """Get route history for a vessel.

    Supports multiple time range formats:
    - ?hours=24 — last N hours
    - ?days=7 — last N days
    - ?from=2025-01-01T00:00:00&to=2025-01-07T00:00:00 — specific range

    Returns positions ordered by timestamp ascending.
    """
    engine = _get_engine()

    # Get from local database
    track = await asyncio.to_thread(
        engine.db.get_track,
        imo,
        hours=hours,
        days=days,
        from_time=from_time,
        to_time=to_time,
    )

    # If no local data, try provider's track API
    if not track:
        provider_track = await engine.provider.get_vessel_track(
            imo, hours=hours or (days * 24 if days else 24)
        )
        if provider_track:
            track = provider_track

    return {
        "imo_number": imo,
        "positions": track,
        "count": len(track),
    }


@vessel_router.post("/watchlist/reload")
async def reload_watchlist() -> dict:
    """Force reload of the watchlist CSV.

    Useful after manually editing the CSV file.
    """
    engine = _get_engine()
    # Reset mtime to force reload
    engine._watchlist_mtime = 0.0
    entries = engine.load_watchlist()

    # If using demo provider, update it with new watchlist
    from app.ingestion.ais.demo_provider import DemoAISProvider
    if isinstance(engine.provider, DemoAISProvider):
        engine.provider.update_watchlist([e.imo_number for e in entries])

    return {
        "status": "reloaded",
        "vessel_count": len(entries),
        "vessels": [
            {"imo_number": e.imo_number, "vessel_name": e.vessel_name}
            for e in entries
        ],
    }


@vessel_router.post("/{imo}/link")
async def link_vessel(imo: str, req: VesselLinkRequest) -> dict:
    """Link a vessel to a supplier and/or shipment (API alternative to CSV editing).

    Note: This updates the in-memory watchlist only. For persistent changes,
    edit the watchlist CSV directly.
    """
    engine = _get_engine()

    # Find or create watchlist entry
    entry = next((w for w in engine._watchlist if w.imo_number == imo), None)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"IMO {imo} not in watchlist. Add it to watchlist.csv first.",
        )

    if req.linked_supplier is not None:
        entry.linked_supplier = req.linked_supplier
    if req.linked_shipment_id is not None:
        entry.linked_shipment_id = req.linked_shipment_id

    return {
        "imo_number": imo,
        "linked_supplier": entry.linked_supplier,
        "linked_shipment_id": entry.linked_shipment_id,
        "note": "In-memory only. Edit watchlist.csv for persistence.",
    }
