"""
Vessel tracking API endpoints.

Integrates with the AIS engine, vessel database, and real-time live AIS provider.
Supports database-backed dynamic vessel tracking (no static CSV requirement).
"""

import asyncio
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.ingestion.ais.vessel_worker import get_vessel_worker

logger = logging.getLogger(__name__)

vessel_router = APIRouter(prefix="/vessels", tags=["vessels"])


# ==================== REQUEST/RESPONSE MODELS ====================


class VesselLinkRequest(BaseModel):
    """Request to link a vessel to a supplier/shipment."""
    linked_supplier: Optional[str] = None
    linked_shipment_id: Optional[str] = None


class TrackVesselRequest(BaseModel):
    """Request to dynamically track a vessel in real time."""
    identifier: str  # IMO number or MMSI
    mmsi: Optional[str] = None
    vessel_name: Optional[str] = None
    linked_supplier: Optional[str] = None
    linked_shipment_id: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    notes: Optional[str] = None
    material: Optional[str] = None
    quantity: Optional[float] = None
    lead_time_days: Optional[float] = None
    inventory_days_cover: Optional[float] = None
    declared_value_usd: Optional[float] = None
    priority: Optional[str] = None


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
    """Get all watched vessels with real-time status and identity.

    Returns fleet summary and list of all tracked vessels with their
    current position, status indicator, and linked supplier/shipment info.
    """
    engine = _get_engine()
    statuses = engine.get_all_vessel_statuses()
    fleet = engine.get_fleet_status()
    provider = os.getenv("AIS_PROVIDER", "demo").lower()
    is_live = bool(os.getenv("AIS_API_KEY", "").strip()) and provider != "demo"

    return {
        "fleet_summary": fleet,
        "vessels": statuses,
        "provider": provider,
        "is_live": is_live,
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
    """Search for vessels by name or number across live AIS database.

    Useful for finding IMO/MMSI numbers to add to dynamic tracking.
    """
    engine = _get_engine()
    results = await engine.provider.search_vessel(q)
    return {
        "query": q,
        "results": results[:20],
        "count": len(results),
    }


@vessel_router.post("/track")
async def track_vessel(req: TrackVesselRequest) -> dict:
    """Dynamically add any vessel to real-time tracking (saved directly to SQLite)."""
    engine = _get_engine()
    kwargs = {}
    if req.material: kwargs["material"] = req.material
    if req.quantity: kwargs["quantity"] = req.quantity
    if req.lead_time_days: kwargs["lead_time_days"] = req.lead_time_days
    if req.inventory_days_cover: kwargs["inventory_days_cover"] = req.inventory_days_cover
    if req.declared_value_usd: kwargs["declared_value_usd"] = req.declared_value_usd
    if req.priority: kwargs["priority"] = req.priority

    result = await engine.add_tracked_vessel(
        identifier=req.identifier,
        mmsi=req.mmsi or "",
        vessel_name=req.vessel_name or "",
        linked_supplier=req.linked_supplier or "",
        linked_shipment_id=req.linked_shipment_id or "",
        origin=req.origin or "",
        destination=req.destination or "",
        notes=req.notes or "",
        **kwargs,
    )
    return {"status": "tracked", "vessel": result}


@vessel_router.delete("/{identifier}")
async def untrack_vessel(identifier: str) -> dict:
    """Remove a vessel from active tracking."""
    engine = _get_engine()
    success = await engine.remove_tracked_vessel(identifier)
    if not success:
        raise HTTPException(status_code=404, detail=f"Vessel {identifier} not found in tracking")

    # Clean up cached shipment analysis if present
    try:
        from app.api.routes import _shipment_analysis_cache
        keys_to_del = [k for k in _shipment_analysis_cache if identifier in k]
        for k in keys_to_del:
            _shipment_analysis_cache.pop(k, None)
    except Exception:
        pass

    return {"status": "untracked", "identifier": identifier}


@vessel_router.post("/refresh")
async def refresh_fleet() -> dict:
    """Trigger an immediate real-time AIS poll for all tracked vessels."""
    engine = _get_engine()
    updated = await engine.poll_once()
    return {
        "status": "refreshed",
        "updated_count": len(updated),
        "fleet_summary": engine.get_fleet_status(),
    }


@vessel_router.get("/resolve/{imo}")
async def resolve_vessel(imo: str) -> dict:
    """Resolve an IMO or MMSI number to full vessel identity."""
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

    raise HTTPException(status_code=404, detail=f"Could not resolve identifier {imo}")


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
        raise HTTPException(status_code=404, detail=f"No data for identifier {imo}")

    return status


@vessel_router.get("/{imo}/track")
async def get_vessel_track(
    imo: str,
    hours: Optional[int] = Query(None, ge=1, le=720),
    days: Optional[int] = Query(None, ge=1, le=90),
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
) -> dict:
    """Get route history for a vessel."""
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

    normalized_track = []
    for p in (track or []):
        lat = p.get("lat") if p.get("lat") is not None else p.get("latitude")
        lon = p.get("lon") if p.get("lon") is not None else p.get("longitude")
        normalized_track.append({
            **p,
            "latitude": lat,
            "longitude": lon,
            "lat": lat,
            "lon": lon,
        })

    return {
        "imo_number": imo,
        "positions": normalized_track,
        "count": len(normalized_track),
    }


@vessel_router.post("/watchlist/reload")
async def reload_watchlist() -> dict:
    """Force reload of the tracked vessels."""
    engine = _get_engine()
    entries = engine.load_watchlist()
    return {
        "status": "reloaded",
        "vessel_count": len(entries),
        "vessels": [
            {"imo_number": e.imo_number, "mmsi": e.mmsi, "vessel_name": e.vessel_name}
            for e in entries
        ],
    }


@vessel_router.post("/{imo}/link")
async def link_vessel(imo: str, req: VesselLinkRequest) -> dict:
    """Link a vessel to a supplier and/or shipment."""
    engine = _get_engine()
    entry = next((w for w in engine._watchlist if w.imo_number == imo or w.mmsi == imo), None)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Vessel {imo} not found in tracked vessels.",
        )

    supplier = req.linked_supplier if req.linked_supplier is not None else entry.linked_supplier
    shipment_id = req.linked_shipment_id if req.linked_shipment_id is not None else entry.linked_shipment_id

    await asyncio.to_thread(
        engine.db.upsert_tracked_vessel,
        imo_number=entry.imo_number,
        mmsi=entry.mmsi,
        vessel_name=entry.vessel_name,
        linked_supplier=supplier,
        linked_shipment_id=shipment_id,
        origin=entry.origin,
        destination=entry.destination,
        notes=entry.notes,
    )
    engine.load_watchlist()

    return {
        "imo_number": imo,
        "linked_supplier": supplier,
        "linked_shipment_id": shipment_id,
    }
