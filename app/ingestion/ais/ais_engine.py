"""
AIS Data Engine — async vessel tracking with watchlist management.

Adapted from maritime_ai_platform/ais/ais_engine.py:
- Converted from QThread-based to asyncio background task
- Added CSV watchlist reading with hot-reload (file mtime check)
- Staggers API requests across polling interval for 60 vessels
- Integrates with risk engine, WebSocket alerts, and playbook system
- Stores positions in SQLite for route history
"""

import asyncio
import csv
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.ingestion.ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_WATCHLIST_PATH = "./watchlist.csv"
DEFAULT_DB_PATH = "./data/vessel_tracking.db"


class WatchlistEntry:
    """A single vessel in the watchlist CSV."""

    def __init__(
        self,
        imo_number: str = "",
        mmsi: str = "",
        vessel_name: str = "",
        linked_supplier: str = "",
        linked_shipment_id: str = "",
        notes: str = "",
    ):
        self.imo_number = imo_number.strip()
        self.mmsi = mmsi.strip()
        self.vessel_name = vessel_name.strip()
        self.linked_supplier = linked_supplier.strip()
        self.linked_shipment_id = linked_shipment_id.strip()
        self.notes = notes.strip()


class VesselDatabase:
    """Thread-safe SQLite database for vessel positions and identities.

    Adapted from maritime_ai_platform/database/db_manager.py patterns:
    - WAL mode for concurrent reads
    - Thread-local connections
    - Auto-purge of old records
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=30)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS vessel_identities (
                imo_number TEXT PRIMARY KEY,
                mmsi TEXT,
                vessel_name TEXT,
                flag TEXT,
                vessel_type TEXT,
                length REAL,
                beam REAL,
                draught REAL,
                call_sign TEXT,
                year_built INTEGER,
                dwt REAL,
                resolved_at DATETIME,
                raw_data TEXT
            );

            CREATE TABLE IF NOT EXISTS vessel_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imo_number TEXT NOT NULL,
                mmsi TEXT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                speed REAL,
                course REAL,
                heading REAL,
                nav_status TEXT,
                destination TEXT,
                eta TEXT,
                timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_vessel_pos_imo_time
                ON vessel_positions(imo_number, timestamp);

            CREATE INDEX IF NOT EXISTS idx_vessel_pos_timestamp
                ON vessel_positions(timestamp);
        """)
        conn.commit()
        logger.info(f"Vessel database initialized at {self.db_path}")

    def store_position(self, vessel: dict[str, Any]) -> None:
        """Store a vessel position record."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO vessel_positions
                (imo_number, mmsi, lat, lon, speed, course, heading,
                 nav_status, destination, eta, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vessel.get("imo_number", ""),
            vessel.get("mmsi", ""),
            vessel.get("latitude", 0),
            vessel.get("longitude", 0),
            vessel.get("speed", 0),
            vessel.get("course", 0),
            vessel.get("heading", 0),
            vessel.get("nav_status", ""),
            vessel.get("destination", ""),
            vessel.get("eta", ""),
            vessel.get("last_update") or datetime.utcnow().isoformat(),
        ))
        conn.commit()

    def get_track(
        self, imo_number: str, hours: int | None = None, days: int | None = None,
        from_time: str | None = None, to_time: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get position history for a vessel."""
        conn = self._get_conn()

        if from_time and to_time:
            cursor = conn.execute(
                "SELECT * FROM vessel_positions WHERE imo_number=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp",
                (imo_number, from_time, to_time),
            )
        elif hours:
            since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            cursor = conn.execute(
                "SELECT * FROM vessel_positions WHERE imo_number=? AND timestamp>=? ORDER BY timestamp",
                (imo_number, since),
            )
        elif days:
            since = (datetime.utcnow() - timedelta(days=days)).isoformat()
            cursor = conn.execute(
                "SELECT * FROM vessel_positions WHERE imo_number=? AND timestamp>=? ORDER BY timestamp",
                (imo_number, since),
            )
        else:
            # Default: last 24 hours
            since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            cursor = conn.execute(
                "SELECT * FROM vessel_positions WHERE imo_number=? AND timestamp>=? ORDER BY timestamp",
                (imo_number, since),
            )

        return [dict(row) for row in cursor.fetchall()]

    def upsert_identity(self, vessel: dict[str, Any]) -> None:
        """Cache vessel identity information."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO vessel_identities
                (imo_number, mmsi, vessel_name, flag, vessel_type, length, beam,
                 draught, call_sign, year_built, dwt, resolved_at, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(imo_number) DO UPDATE SET
                mmsi=excluded.mmsi, vessel_name=excluded.vessel_name,
                flag=excluded.flag, vessel_type=excluded.vessel_type,
                length=excluded.length, beam=excluded.beam, draught=excluded.draught,
                call_sign=excluded.call_sign, year_built=excluded.year_built,
                dwt=excluded.dwt, resolved_at=excluded.resolved_at,
                raw_data=excluded.raw_data
        """, (
            vessel.get("imo_number", ""),
            vessel.get("mmsi", ""),
            vessel.get("name", ""),
            vessel.get("flag", ""),
            vessel.get("vessel_type", ""),
            vessel.get("length", 0),
            vessel.get("beam", 0),
            vessel.get("draught", 0),
            vessel.get("call_sign", ""),
            vessel.get("year_built"),
            vessel.get("dwt"),
            datetime.utcnow().isoformat(),
            json.dumps(vessel),
        ))
        conn.commit()

    def get_identity(self, imo_number: str) -> dict[str, Any] | None:
        """Get cached vessel identity."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM vessel_identities WHERE imo_number=?", (imo_number,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_identities(self) -> list[dict[str, Any]]:
        """Get all cached vessel identities."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM vessel_identities")
        return [dict(row) for row in cursor.fetchall()]

    def purge_old_positions(self, retention_days: int = 90) -> int:
        """Delete positions older than retention period."""
        conn = self._get_conn()
        cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
        cursor = conn.execute(
            "DELETE FROM vessel_positions WHERE timestamp < ?", (cutoff,)
        )
        conn.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Purged {deleted} vessel positions older than {retention_days} days")
        return deleted

    def get_latest_position(self, imo_number: str) -> dict[str, Any] | None:
        """Get the most recent position for a vessel."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM vessel_positions WHERE imo_number=? ORDER BY timestamp DESC LIMIT 1",
            (imo_number,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


class AISEngine:
    """
    Main AIS engine — manages providers, watchlist, polling, and anomaly detection.

    Integrates with:
    - AIS providers (AISHub, MarineTraffic, Demo)
    - Vessel position database
    - Risk engine (via callbacks)
    - WebSocket manager (via callbacks)
    """

    def __init__(
        self,
        provider: AISProviderBase,
        db: VesselDatabase | None = None,
        watchlist_path: str = DEFAULT_WATCHLIST_PATH,
        poll_interval: int = 300,
        silence_threshold_hours: float = 6.0,
        stale_threshold_hours: float = 1.0,
    ):
        self.provider = provider
        self.db = db or VesselDatabase()
        self.watchlist_path = watchlist_path
        self.poll_interval = poll_interval
        self.silence_threshold_hours = silence_threshold_hours
        self.stale_threshold_hours = stale_threshold_hours

        # Watchlist state
        self._watchlist: list[WatchlistEntry] = []
        self._watchlist_mtime: float = 0.0

        # Current vessel states (IMO → latest data)
        self._vessel_states: dict[str, dict[str, Any]] = {}

        # Anomaly callbacks
        self._on_anomaly: list[Any] = []
        self._on_position_update: list[Any] = []

        # Danger zones (loaded from JSON)
        self._danger_zones: list[dict[str, Any]] = []
        self._load_danger_zones()

        # Previous states for anomaly detection
        self._previous_speeds: dict[str, list[float]] = {}

    def _load_danger_zones(self) -> None:
        """Load danger zone definitions from JSON."""
        zones_path = Path(__file__).parent / "danger_zones.json"
        try:
            with open(zones_path) as f:
                geojson = json.load(f)
            for feature in geojson.get("features", []):
                props = feature.get("properties", {})
                coords = feature.get("geometry", {}).get("coordinates", [[]])[0]
                if coords:
                    lons = [c[0] for c in coords]
                    lats = [c[1] for c in coords]
                    self._danger_zones.append({
                        "name": props.get("name", "Unknown"),
                        "risk_weight": props.get("risk_weight", 15),
                        "lat_min": min(lats),
                        "lat_max": max(lats),
                        "lon_min": min(lons),
                        "lon_max": max(lons),
                    })
            logger.info(f"Loaded {len(self._danger_zones)} danger zones")
        except Exception as e:
            logger.warning(f"Failed to load danger zones: {e}")

    def on_anomaly(self, callback) -> None:
        """Register a callback for anomaly events."""
        self._on_anomaly.append(callback)

    def on_position_update(self, callback) -> None:
        """Register a callback for position updates."""
        self._on_position_update.append(callback)

    def load_watchlist(self) -> list[WatchlistEntry]:
        """Load or reload the watchlist CSV.

        Hot-reload: checks file mtime and only reloads if changed.
        Supports entries with IMO number, MMSI, or both.
        """
        path = Path(self.watchlist_path)
        if not path.exists():
            logger.warning(f"Watchlist not found: {self.watchlist_path}")
            return self._watchlist

        try:
            mtime = path.stat().st_mtime
            if mtime == self._watchlist_mtime and self._watchlist:
                return self._watchlist  # No change

            entries = []
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    imo = row.get("imo_number", "").strip()
                    mmsi = row.get("mmsi", "").strip()
                    if (not imo and not mmsi) or imo.startswith("#"):
                        continue
                    entries.append(WatchlistEntry(
                        imo_number=imo,
                        mmsi=mmsi,
                        vessel_name=row.get("vessel_name", ""),
                        linked_supplier=row.get("linked_supplier", ""),
                        linked_shipment_id=row.get("linked_shipment_id", ""),
                        notes=row.get("notes", ""),
                    ))

            self._watchlist = entries
            self._watchlist_mtime = mtime
            logger.info(f"Watchlist loaded: {len(entries)} vessels from {self.watchlist_path}")
            return entries

        except Exception as e:
            logger.error(f"Failed to load watchlist: {e}")
            return self._watchlist

    async def poll_once(self) -> list[dict[str, Any]]:
        """Perform a single polling cycle for all watchlist vessels.

        Supports both IMO and MMSI-based lookups. For AISStream provider,
        vessels are looked up by MMSI since that's the AIS primary key.
        """
        watchlist = self.load_watchlist()
        if not watchlist:
            logger.info("No vessels in watchlist, skipping poll")
            return []

        # Build lookup keys — use MMSI if no IMO available
        vessel_keys = []
        for entry in watchlist:
            key = entry.imo_number or entry.mmsi
            if key:
                vessel_keys.append((key, entry))

        stagger_delay = self.poll_interval / max(len(vessel_keys), 1)
        updated_vessels = []

        # For AISStream, try batch fetch first (reads from cache)
        from app.ingestion.ais.aisstream_provider import AISStreamProvider
        if isinstance(self.provider, AISStreamProvider):
            # Start streaming if not already running
            if not self.provider._running:
                await self.provider.start_streaming()
                # Give it time to connect and receive initial data
                await asyncio.sleep(5)

            # AISStream streams data continuously — just read from its cache
            # The provider's MMSI cache is populated by the WebSocket stream
            for key, entry in vessel_keys:
                mmsi = entry.mmsi
                vessel = None

                # Try MMSI cache directly
                if mmsi and mmsi in self.provider._mmsi_cache:
                    vessel = self.provider._mmsi_cache[mmsi]
                elif entry.imo_number:
                    vessel = self.provider._vessel_cache.get(entry.imo_number)

                if vessel:
                    # Use MMSI as the state key if no IMO
                    state_key = entry.imo_number or entry.mmsi
                    vessel["imo_number"] = entry.imo_number or ""
                    vessel["mmsi"] = entry.mmsi or vessel.get("mmsi", "")
                    self._vessel_states[state_key] = vessel

                    # Store position in database
                    await asyncio.to_thread(self.db.store_position, vessel)

                    # Check for anomalies
                    anomalies = self._check_anomalies(state_key, vessel)
                    for anomaly in anomalies:
                        for callback in self._on_anomaly:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(anomaly)
                                else:
                                    callback(anomaly)
                            except Exception as e:
                                logger.error(f"Anomaly callback error: {e}")

                    # Notify position update callbacks
                    for callback in self._on_position_update:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(vessel)
                            else:
                                callback(vessel)
                        except Exception as e:
                            logger.error(f"Position update callback error: {e}")

                    updated_vessels.append(vessel)

            logger.info(f"Poll complete: {len(updated_vessels)}/{len(vessel_keys)} vessels updated")
            return updated_vessels

        # For other providers (AISHub, MarineTraffic) — poll by IMO
        for i, (key, entry) in enumerate(vessel_keys):
            if i > 0 and stagger_delay > 0.5:
                await asyncio.sleep(min(stagger_delay, 5.0))

            try:
                vessel = await self.provider.get_vessel_by_imo(key)
                if vessel:
                    vessel["imo_number"] = key  # Ensure key is set
                    self._vessel_states[key] = vessel

                    # Store position in database
                    await asyncio.to_thread(self.db.store_position, vessel)

                    # Cache identity if not already cached
                    identity = await asyncio.to_thread(self.db.get_identity, key)
                    if not identity:
                        await asyncio.to_thread(self.db.upsert_identity, vessel)

                    # Check for anomalies
                    anomalies = self._check_anomalies(key, vessel)
                    for anomaly in anomalies:
                        for callback in self._on_anomaly:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(anomaly)
                                else:
                                    callback(anomaly)
                            except Exception as e:
                                logger.error(f"Anomaly callback error: {e}")

                    # Notify position update callbacks
                    for callback in self._on_position_update:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(vessel)
                            else:
                                callback(vessel)
                        except Exception as e:
                            logger.error(f"Position update callback error: {e}")

                    updated_vessels.append(vessel)
                else:
                    logger.debug(f"No data returned for {key}")

            except Exception as e:
                logger.error(f"Error polling {key}: {e}")

        logger.info(f"Poll complete: {len(updated_vessels)}/{len(vessel_keys)} vessels updated")
        return updated_vessels

    def _check_anomalies(self, imo: str, vessel: dict[str, Any]) -> list[dict[str, Any]]:
        """Check for vessel anomalies: AIS silence, speed anomaly, danger zone entry."""
        anomalies = []
        watchlist_entry = next(
            (w for w in self._watchlist if w.imo_number == imo or w.mmsi == imo),
            None,
        )
        vessel_name = vessel.get("name") or (watchlist_entry.vessel_name if watchlist_entry else imo)

        # 1. AIS Silence Detection
        last_update = vessel.get("last_update", "")
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                silence_hours = (datetime.utcnow() - last_time.replace(tzinfo=None)).total_seconds() / 3600
                if silence_hours >= self.silence_threshold_hours:
                    anomalies.append({
                        "type": "ais_silence",
                        "imo_number": imo,
                        "vessel_name": vessel_name,
                        "severity": "high",
                        "message": f"AIS signal lost for {vessel_name} — {silence_hours:.1f} hours",
                        "details": f"Last position: {vessel.get('latitude', 0):.4f}N, {vessel.get('longitude', 0):.4f}E",
                        "silence_hours": silence_hours,
                        "linked_supplier": watchlist_entry.linked_supplier if watchlist_entry else "",
                        "linked_shipment_id": watchlist_entry.linked_shipment_id if watchlist_entry else "",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
            except (ValueError, TypeError):
                pass

        # 2. Speed Anomaly Detection
        current_speed = vessel.get("speed", 0)
        speed_history = self._previous_speeds.setdefault(imo, [])
        if len(speed_history) >= 5:
            avg_speed = sum(speed_history[-6:]) / len(speed_history[-6:])
            speed_change = abs(current_speed - avg_speed)
            # Only flag if change is > 50% of average AND > 8 knots absolute change
            if speed_change > 8.0 and avg_speed > 2.0 and speed_change > avg_speed * 0.5:
                anomalies.append({
                    "type": "speed_anomaly",
                    "imo_number": imo,
                    "vessel_name": vessel_name,
                    "severity": "medium" if speed_change < 12 else "high",
                    "message": f"Speed anomaly on {vessel_name}: {avg_speed:.1f} → {current_speed:.1f} kts",
                    "details": f"Change of {speed_change:.1f} knots from 6-point average",
                    "current_speed": current_speed,
                    "average_speed": avg_speed,
                    "linked_supplier": watchlist_entry.linked_supplier if watchlist_entry else "",
                    "linked_shipment_id": watchlist_entry.linked_shipment_id if watchlist_entry else "",
                    "timestamp": datetime.utcnow().isoformat(),
                })
        speed_history.append(current_speed)
        if len(speed_history) > 12:
            self._previous_speeds[imo] = speed_history[-12:]

        # 3. Danger Zone Detection
        lat = vessel.get("latitude", 0)
        lon = vessel.get("longitude", 0)
        for zone in self._danger_zones:
            if (zone["lat_min"] <= lat <= zone["lat_max"] and
                    zone["lon_min"] <= lon <= zone["lon_max"]):
                anomalies.append({
                    "type": "danger_zone_entry",
                    "imo_number": imo,
                    "vessel_name": vessel_name,
                    "severity": "high" if zone["risk_weight"] >= 25 else "medium",
                    "message": f"{vessel_name} in danger zone: {zone['name']}",
                    "details": f"Position: {lat:.4f}N, {lon:.4f}E | Zone risk weight: {zone['risk_weight']}",
                    "zone_name": zone["name"],
                    "risk_weight": zone["risk_weight"],
                    "linked_supplier": watchlist_entry.linked_supplier if watchlist_entry else "",
                    "linked_shipment_id": watchlist_entry.linked_shipment_id if watchlist_entry else "",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                break  # Only report first matching zone

        return anomalies

    def get_vessel_status(self, imo: str) -> dict[str, Any] | None:
        """Get current status for a vessel including risk indicators."""
        vessel = self._vessel_states.get(imo)
        if not vessel:
            return None

        # Determine status color
        status = "active"  # 🟢
        last_update = vessel.get("last_update", "")
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                hours_since = (datetime.utcnow() - last_time.replace(tzinfo=None)).total_seconds() / 3600
                if hours_since >= self.silence_threshold_hours:
                    status = "silent"  # 🔴
                elif hours_since >= self.stale_threshold_hours:
                    status = "stale"  # 🟡
            except (ValueError, TypeError):
                pass

        # Check if in danger zone
        in_danger_zone = None
        lat = vessel.get("latitude", 0)
        lon = vessel.get("longitude", 0)
        for zone in self._danger_zones:
            if (zone["lat_min"] <= lat <= zone["lat_max"] and
                    zone["lon_min"] <= lon <= zone["lon_max"]):
                in_danger_zone = zone["name"]
                status = "danger"  # 🔴
                break

        # Find watchlist entry for linked data
        watchlist_entry = next((w for w in self._watchlist if w.imo_number == imo or w.mmsi == imo), None)

        return {
            **vessel,
            "status": status,
            "in_danger_zone": in_danger_zone,
            "linked_supplier": watchlist_entry.linked_supplier if watchlist_entry else None,
            "linked_shipment_id": watchlist_entry.linked_shipment_id if watchlist_entry else None,
        }

    def get_fleet_status(self) -> dict[str, Any]:
        """Get summary of fleet status."""
        active = 0
        stale = 0
        silent = 0
        in_danger_zone = 0

        for imo in [w.imo_number or w.mmsi for w in self._watchlist]:
            status = self.get_vessel_status(imo)
            if not status:
                continue
            s = status.get("status", "active")
            if s == "active":
                active += 1
            elif s == "stale":
                stale += 1
            elif s in ("silent", "danger"):
                if status.get("in_danger_zone"):
                    in_danger_zone += 1
                if s == "silent":
                    silent += 1

        return {
            "total": len(self._watchlist),
            "active": active,
            "stale": stale,
            "silent": silent,
            "in_danger_zone": in_danger_zone,
        }

    def get_all_vessel_statuses(self) -> list[dict[str, Any]]:
        """Get status for all watchlist vessels."""
        results = []
        for entry in self._watchlist:
            key = entry.imo_number or entry.mmsi
            status = self.get_vessel_status(key)
            if status:
                results.append(status)
            else:
                # Vessel not yet polled — return minimal info from watchlist
                results.append({
                    "imo_number": entry.imo_number,
                    "mmsi": entry.mmsi,
                    "name": entry.vessel_name,
                    "status": "unknown",
                    "linked_supplier": entry.linked_supplier,
                    "linked_shipment_id": entry.linked_shipment_id,
                })
        return results

    def get_danger_zones(self) -> list[dict[str, Any]]:
        """Get danger zone definitions with current vessel counts."""
        zones = []
        for zone in self._danger_zones:
            vessels_inside = []
            for imo, vessel in self._vessel_states.items():
                lat = vessel.get("latitude", 0)
                lon = vessel.get("longitude", 0)
                if (zone["lat_min"] <= lat <= zone["lat_max"] and
                        zone["lon_min"] <= lon <= zone["lon_max"]):
                    vessels_inside.append(imo)
            zones.append({
                **zone,
                "vessels_inside": vessels_inside,
                "vessel_count": len(vessels_inside),
            })
        return zones
