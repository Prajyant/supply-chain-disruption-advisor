"""
AIS Data Engine — async vessel tracking with database-backed dynamic fleet management.

Features:
- Real-time live AIS ingestion from providers (VesselAPI, AISStream, AISHub, etc.)
- Database-backed dynamic fleet management (SQLite tracked_vessels table) — no CSV dependency
- Real-time polling and anomaly detection (AIS silence, speed changes, danger zones)
- Position history persistence and thread-safe SQLite connection
- WebSocket position streaming and anomaly broadcasts
"""

import asyncio
import csv
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.ingestion.ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_WATCHLIST_PATH = str(BASE_DIR / "watchlist.csv")
DEFAULT_DB_PATH = str(BASE_DIR / "data" / "vessel_tracking.db")

# Core real-world active commercial fleet initial seed
INITIAL_FLEET_SEED = [
    {
        "imo_number": "9404091",
        "mmsi": "305268000",
        "vessel_name": "HENRIKE SCHEPERS",
        "linked_supplier": "Henrike Logistics",
        "linked_shipment_id": "SHP-2002",
        "origin": "Rotterdam",
        "destination": "Southampton",
        "notes": "North Sea feeder route",
    },
    {
        "imo_number": "9422598",
        "mmsi": "256995000",
        "vessel_name": "CMA CGM SHANGHAI",
        "linked_supplier": "CMA CGM Shipping",
        "linked_shipment_id": "SHP-2001",
        "origin": "Shanghai",
        "destination": "Los Angeles",
        "notes": "Trans-Pacific critical lane",
    },
    {
        "imo_number": "8908868",
        "mmsi": "636023858",
        "vessel_name": "ATLANTIC KLIPPER",
        "linked_supplier": "Atlantic Shipping",
        "linked_shipment_id": "SHP-2003",
        "origin": "Antwerp",
        "destination": "Felixstowe",
        "notes": "English Channel transit",
    },
    {
        "imo_number": "9349028",
        "mmsi": "304972000",
        "vessel_name": "ALDEBARAN J",
        "linked_supplier": "Aldebaran Transport",
        "linked_shipment_id": "SHP-2004",
        "origin": "Hamburg",
        "destination": "Gothenburg",
        "notes": "Baltic Sea corridor",
    },
    {
        "imo_number": "9931329",
        "mmsi": "255915000",
        "vessel_name": "WILSON FLEX I",
        "linked_supplier": "Wilson Line",
        "linked_shipment_id": "SHP-2005",
        "origin": "Gdansk",
        "destination": "Stockholm",
        "notes": "Baltic trade",
    },
    {
        "imo_number": "9811000",
        "mmsi": "353136000",
        "vessel_name": "EVER GIVEN",
        "linked_supplier": "Evergreen Marine",
        "linked_shipment_id": "SHP-1001",
        "origin": "Yantian",
        "destination": "Rotterdam",
        "notes": "Suez Canal lane",
    },
    {
        "imo_number": "9703291",
        "mmsi": "355906000",
        "vessel_name": "MSC OSCAR",
        "linked_supplier": "Mediterranean Shipping Co",
        "linked_shipment_id": "SHP-1002",
        "origin": "Singapore",
        "destination": "Felixstowe",
        "notes": "Malacca & Indian Ocean transit",
    },
    {
        "imo_number": "9619907",
        "mmsi": "219018271",
        "vessel_name": "MAERSK MC-KINNEY MOLLER",
        "linked_supplier": "Maersk Line",
        "linked_shipment_id": "SHP-1003",
        "origin": "Busan",
        "destination": "Bremerhaven",
        "notes": "Asia-Europe express",
    },
    {
        "imo_number": "9795610",
        "mmsi": "477169400",
        "vessel_name": "COSCO SHIPPING UNIVERSE",
        "linked_supplier": "COSCO Shipping",
        "linked_shipment_id": "SHP-1004",
        "origin": "Ningbo",
        "destination": "Antwerp",
        "notes": "Major container route",
    },
    {
        "imo_number": "9863297",
        "mmsi": "351407000",
        "vessel_name": "HMM ALGECIRAS",
        "linked_supplier": "HMM Logistics",
        "linked_shipment_id": "SHP-1005",
        "origin": "Qingdao",
        "destination": "Hamburg",
        "notes": "Suez / Bab-el-Mandeb monitoring",
    },
    {
        "imo_number": "9345386",
        "mmsi": "230350000",
        "vessel_name": "LAURA",
        "linked_supplier": "Laura Shipping",
        "linked_shipment_id": "SHP-2006",
        "origin": "Malmo",
        "destination": "Kiel",
        "notes": "Baltic route",
    },
    {
        "imo_number": "9341603",
        "mmsi": "431008812",
        "vessel_name": "OOZU MARU",
        "linked_supplier": "Oozu Maritime",
        "linked_shipment_id": "SHP-2007",
        "origin": "Kobe",
        "destination": "Osaka",
        "notes": "East Asia coastal trade",
    },
    {
        "imo_number": "9591961",
        "mmsi": "244857000",
        "vessel_name": "CORAL SIDEREA",
        "linked_supplier": "Coral LNG",
        "linked_shipment_id": "SHP-2008",
        "origin": "Stavanger",
        "destination": "Esbjerg",
        "notes": "LNG tanker route",
    },
    {
        "imo_number": "9243227",
        "mmsi": "224729000",
        "vessel_name": "CIUDAD DE SOLLER",
        "linked_supplier": "Ciudad Ferries",
        "linked_shipment_id": "SHP-2009",
        "origin": "Valencia",
        "destination": "Palma",
        "notes": "Western Mediterranean transit",
    },
    {
        "imo_number": "9369069",
        "mmsi": "710001600",
        "vessel_name": "FORTE DE SAO MARCOS",
        "linked_supplier": "Forte Shipping",
        "linked_shipment_id": "SHP-2010",
        "origin": "Recife",
        "destination": "Salvador",
        "notes": "South American Atlantic lane",
    },
    {
        "imo_number": "9283954",
        "mmsi": "265055000",
        "vessel_name": "WAY FORWARD",
        "linked_supplier": "Way Forward Ltd",
        "linked_shipment_id": "SHP-2011",
        "origin": "Southampton",
        "destination": "Rotterdam",
        "notes": "Cross-channel feeder",
    },
    {
        "imo_number": "9388833",
        "mmsi": "215389000",
        "vessel_name": "CGAS MASTER",
        "linked_supplier": "CGAS Maritime",
        "linked_shipment_id": "SHP-2012",
        "origin": "Rotterdam",
        "destination": "Immingham",
        "notes": "Chemical tanker North Sea route",
    },
    {
        "imo_number": "9244001",
        "mmsi": "257095920",
        "vessel_name": "FJORDJARL",
        "linked_supplier": "Fjord Express",
        "linked_shipment_id": "SHP-2013",
        "origin": "Tromso",
        "destination": "Harstad",
        "notes": "Norwegian coastal cargo",
    },
    {
        "imo_number": "9358486",
        "mmsi": "235053701",
        "vessel_name": "PHENIX",
        "linked_supplier": "Phenix Transport",
        "linked_shipment_id": "SHP-2015",
        "origin": "Portsmouth",
        "destination": "Le Havre",
        "notes": "Channel freight link",
    },
    {
        "imo_number": "9789233",
        "mmsi": "368433550",
        "vessel_name": "J THEMISTOCLIS MORAN",
        "linked_supplier": "Moran Towing",
        "linked_shipment_id": "SHP-2016",
        "origin": "Houston",
        "destination": "Galveston",
        "notes": "US Gulf trade lane",
    },
]


class WatchlistEntry:
    """A tracked vessel entry with identity and supply chain linkage."""

    def __init__(
        self,
        imo_number: str = "",
        mmsi: str = "",
        vessel_name: str = "",
        linked_supplier: str = "",
        linked_shipment_id: str = "",
        origin: str = "",
        destination: str = "",
        notes: str = "",
    ):
        imo = str(imo_number or "").strip()
        m = str(mmsi or "").strip()
        # Guarantee non-empty primary imo_number identifier
        self.imo_number = imo if imo else m
        self.mmsi = m
        self.vessel_name = str(vessel_name or f"Vessel {self.imo_number}").strip()
        self.linked_supplier = str(linked_supplier or "").strip()
        self.linked_shipment_id = str(linked_shipment_id or "").strip()
        self.origin = str(origin or "").strip()
        self.destination = str(destination or "").strip()
        self.notes = str(notes or "").strip()


class VesselDatabase:
    """Thread-safe SQLite database for tracked vessels, positions, and identities."""

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
            CREATE TABLE IF NOT EXISTS tracked_vessels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imo_number TEXT UNIQUE NOT NULL,
                mmsi TEXT,
                vessel_name TEXT,
                linked_supplier TEXT,
                linked_shipment_id TEXT,
                origin TEXT,
                destination TEXT,
                notes TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_tracked_vessels_imo
                ON tracked_vessels(imo_number);

            CREATE INDEX IF NOT EXISTS idx_tracked_vessels_mmsi
                ON tracked_vessels(mmsi);

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
        # Auto-migrate optional shipment columns to tracked_vessels
        shipment_cols = [
            ("material", "TEXT DEFAULT 'Containerized Cargo'"),
            ("quantity", "REAL DEFAULT 1200"),
            ("lead_time_days", "REAL DEFAULT 18"),
            ("inventory_days_cover", "REAL DEFAULT 7"),
            ("supplier_delay_count", "INTEGER DEFAULT 1"),
            ("priority", "TEXT DEFAULT '2'"),
            ("declared_value_usd", "REAL DEFAULT 450000"),
            ("departure_date", "TEXT DEFAULT '2026-04-28'"),
            ("eta_date", "TEXT DEFAULT '2026-05-20'"),
        ]
        for col_name, col_def in shipment_cols:
            try:
                conn.execute(f"ALTER TABLE tracked_vessels ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass
        conn.commit()
        logger.info(f"Vessel database initialized at {self.db_path}")

    def seed_initial_vessels_if_empty(self) -> None:
        """Seed initial commercial vessels linked to supply chain if table is empty."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM tracked_vessels")
        count = cursor.fetchone()[0]
        if count > 0:
            return

        logger.info("Seeding initial live commercial vessels into tracked_vessels table...")
        for item in INITIAL_FLEET_SEED:
            conn.execute("""
                INSERT OR IGNORE INTO tracked_vessels
                    (imo_number, mmsi, vessel_name, linked_supplier, linked_shipment_id, origin, destination, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item["imo_number"],
                item["mmsi"],
                item["vessel_name"],
                item["linked_supplier"],
                item["linked_shipment_id"],
                item["origin"],
                item["destination"],
                item["notes"],
            ))
        conn.commit()
        logger.info(f"Seeded {len(INITIAL_FLEET_SEED)} tracked vessels")

    def get_tracked_vessels(self) -> list[dict[str, Any]]:
        """Get all active tracked vessels from database."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM tracked_vessels WHERE is_active=1 ORDER BY vessel_name ASC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def upsert_tracked_vessel(
        self,
        imo_number: str,
        mmsi: str = "",
        vessel_name: str = "",
        linked_supplier: str = "",
        linked_shipment_id: str = "",
        origin: str = "",
        destination: str = "",
        notes: str = "",
        material: str = "Containerized Cargo",
        quantity: float = 1200.0,
        lead_time_days: float = 18.0,
        inventory_days_cover: float = 7.0,
        supplier_delay_count: int = 1,
        priority: str = "2",
        declared_value_usd: float = 450000.0,
        departure_date: str = "2026-04-28",
        eta_date: str = "2026-05-20",
    ) -> None:
        """Add or update a tracked vessel."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO tracked_vessels
                (imo_number, mmsi, vessel_name, linked_supplier, linked_shipment_id, origin, destination, notes,
                 material, quantity, lead_time_days, inventory_days_cover, supplier_delay_count, priority,
                 declared_value_usd, departure_date, eta_date, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(imo_number) DO UPDATE SET
                mmsi=excluded.mmsi,
                vessel_name=excluded.vessel_name,
                linked_supplier=excluded.linked_supplier,
                linked_shipment_id=excluded.linked_shipment_id,
                origin=excluded.origin,
                destination=excluded.destination,
                notes=excluded.notes,
                material=excluded.material,
                quantity=excluded.quantity,
                lead_time_days=excluded.lead_time_days,
                inventory_days_cover=excluded.inventory_days_cover,
                supplier_delay_count=excluded.supplier_delay_count,
                priority=excluded.priority,
                declared_value_usd=excluded.declared_value_usd,
                departure_date=excluded.departure_date,
                eta_date=excluded.eta_date,
                is_active=1,
                updated_at=excluded.updated_at
        """, (
            imo_number, mmsi, vessel_name, linked_supplier, linked_shipment_id, origin, destination, notes,
            material, quantity, lead_time_days, inventory_days_cover, supplier_delay_count, priority,
            declared_value_usd, departure_date, eta_date, now
        ))
        conn.commit()

    def delete_tracked_vessel(self, identifier: str) -> bool:
        """Untrack/delete a vessel by IMO or MMSI."""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM tracked_vessels WHERE imo_number=? OR mmsi=?",
            (identifier, identifier),
        )
        conn.commit()
        return cursor.rowcount > 0

    def store_position(self, vessel: dict[str, Any]) -> None:
        """Store a vessel position record."""
        conn = self._get_conn()
        imo = str(vessel.get("imo_number") or vessel.get("mmsi") or "").strip()
        if not imo:
            return

        conn.execute("""
            INSERT INTO vessel_positions
                (imo_number, mmsi, lat, lon, speed, course, heading,
                 nav_status, destination, eta, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            imo,
            str(vessel.get("mmsi") or ""),
            float(vessel.get("latitude") or 0.0),
            float(vessel.get("longitude") or 0.0),
            float(vessel.get("speed") or 0.0),
            float(vessel.get("course") or 0.0),
            float(vessel.get("heading") or 0.0),
            str(vessel.get("nav_status") or ""),
            str(vessel.get("destination") or ""),
            str(vessel.get("eta") or ""),
            vessel.get("last_update") or datetime.now(timezone.utc).isoformat(),
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
                "SELECT * FROM vessel_positions WHERE (imo_number=? OR mmsi=?) AND timestamp BETWEEN ? AND ? ORDER BY timestamp",
                (imo_number, imo_number, from_time, to_time),
            )
        elif hours:
            since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            cursor = conn.execute(
                "SELECT * FROM vessel_positions WHERE (imo_number=? OR mmsi=?) AND timestamp>=? ORDER BY timestamp",
                (imo_number, imo_number, since),
            )
        elif days:
            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            cursor = conn.execute(
                "SELECT * FROM vessel_positions WHERE (imo_number=? OR mmsi=?) AND timestamp>=? ORDER BY timestamp",
                (imo_number, imo_number, since),
            )
        else:
            since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            cursor = conn.execute(
                "SELECT * FROM vessel_positions WHERE (imo_number=? OR mmsi=?) AND timestamp>=? ORDER BY timestamp",
                (imo_number, imo_number, since),
            )

        return [dict(row) for row in cursor.fetchall()]

    def upsert_identity(self, vessel: dict[str, Any]) -> None:
        """Cache vessel identity information."""
        conn = self._get_conn()
        imo = str(vessel.get("imo_number") or vessel.get("mmsi") or "").strip()
        if not imo:
            return
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
            imo,
            str(vessel.get("mmsi") or ""),
            str(vessel.get("name") or vessel.get("vessel_name") or ""),
            str(vessel.get("flag") or ""),
            str(vessel.get("vessel_type") or ""),
            float(vessel.get("length") or 0.0),
            float(vessel.get("beam") or 0.0),
            float(vessel.get("draught") or 0.0),
            str(vessel.get("call_sign") or ""),
            vessel.get("year_built"),
            vessel.get("dwt"),
            datetime.now(timezone.utc).isoformat(),
            json.dumps(vessel),
        ))
        conn.commit()

    def get_identity(self, imo_number: str) -> dict[str, Any] | None:
        """Get cached vessel identity."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM vessel_identities WHERE imo_number=? OR mmsi=?",
            (imo_number, imo_number),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_latest_position(self, imo_number: str) -> dict[str, Any] | None:
        """Get the most recent position for a vessel."""
        ident = str(imo_number or "").strip()
        if not ident:
            return None
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM vessel_positions WHERE (imo_number=? OR mmsi=?) AND length(trim(imo_number)) > 0 ORDER BY timestamp DESC LIMIT 1",
            (ident, ident),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def purge_old_positions(self, retention_days: int = 90) -> int:
        """Delete positions older than retention period."""
        conn = self._get_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        cursor = conn.execute(
            "DELETE FROM vessel_positions WHERE timestamp < ?", (cutoff,)
        )
        conn.commit()
        return cursor.rowcount


class AISEngine:
    """Main AIS engine — manages providers, real-time polling, and anomaly detection."""

    def __init__(
        self,
        provider: AISProviderBase,
        db: VesselDatabase | None = None,
        watchlist_path: str = DEFAULT_WATCHLIST_PATH,
        poll_interval: int = 30,
        silence_threshold_hours: float = 6.0,
        stale_threshold_hours: float = 1.0,
    ):
        self.provider = provider
        self.db = db or VesselDatabase()
        self.watchlist_path = watchlist_path
        self.poll_interval = poll_interval
        self.silence_threshold_hours = silence_threshold_hours
        self.stale_threshold_hours = stale_threshold_hours

        # Seed initial vessels if DB is empty
        self.db.seed_initial_vessels_if_empty()

        # In-memory watchlist entries loaded from DB
        self._watchlist: list[WatchlistEntry] = []
        self.load_watchlist()

        # Current vessel states (IMO/MMSI → latest vessel data)
        self._vessel_states: dict[str, dict[str, Any]] = {}

        # Callbacks
        self._on_anomaly: list[Any] = []
        self._on_position_update: list[Any] = []

        # Danger zones
        self._danger_zones: list[dict[str, Any]] = []
        self._load_danger_zones()

        # Speed histories for anomaly detection
        self._previous_speeds: dict[str, list[float]] = {}

    def _load_danger_zones(self) -> None:
        """Load danger zone definitions from JSON."""
        zones_path = Path(__file__).parent / "danger_zones.json"
        try:
            with open(zones_path, encoding="utf-8") as f:
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
        self._on_anomaly.append(callback)

    def on_position_update(self, callback) -> None:
        self._on_position_update.append(callback)

    def load_watchlist(self) -> list[WatchlistEntry]:
        """Load active tracked vessels from database."""
        db_vessels = self.db.get_tracked_vessels()
        entries = []
        for v in db_vessels:
            entries.append(WatchlistEntry(
                imo_number=v.get("imo_number", ""),
                mmsi=v.get("mmsi", ""),
                vessel_name=v.get("vessel_name", ""),
                linked_supplier=v.get("linked_supplier", ""),
                linked_shipment_id=v.get("linked_shipment_id", ""),
                origin=v.get("origin", ""),
                destination=v.get("destination", ""),
                notes=v.get("notes", ""),
            ))
        self._watchlist = entries
        return entries

    async def add_tracked_vessel(
        self,
        identifier: str,
        mmsi: str = "",
        vessel_name: str = "",
        linked_supplier: str = "",
        linked_shipment_id: str = "",
        origin: str = "",
        destination: str = "",
        notes: str = "",
        material: str = "Containerized Cargo",
        quantity: float = 1200.0,
        lead_time_days: float = 18.0,
        inventory_days_cover: float = 7.0,
        supplier_delay_count: int = 1,
        priority: str = "2",
        declared_value_usd: float = 450000.0,
        departure_date: str = "2026-04-28",
        eta_date: str = "2026-05-20",
    ) -> dict[str, Any]:
        """Dynamically add a vessel to real-time tracking."""
        ident = str(identifier).strip()
        m = str(mmsi).strip()
        v_name = str(vessel_name or f"Vessel {ident}").strip()
        supplier = str(linked_supplier or v_name).strip()
        shipment_id = str(linked_shipment_id or f"SHP-{ident}").strip()
        orig = str(origin or "Shanghai").strip()
        dest = str(destination or "Rotterdam").strip()

        # Derive realistic logistics attributes if not customized
        o_low = orig.lower()
        d_low = dest.lower()
        v_up = v_name.upper()
        now_dt = datetime.now(timezone.utc)

        if material == "Containerized Cargo" and lead_time_days == 18.0:
            if ("houston" in o_low and "galveston" in d_low) or ("galveston" in o_low and "houston" in d_low) or ("moran" in v_up):
                material = "Refined Fuel & Petrochemical Barge Tow"
                lead_time_days = 1.0
                inventory_days_cover = 22.0
                supplier_delay_count = 0
                priority = "1"
                declared_value_usd = 185000.0
                quantity = 850.0
            elif any(p in o_low for p in ("rotterdam", "antwerp", "hamburg", "valencia", "kobe")):
                material = "Containerized Automotive & Industrial Assembly Parts"
                lead_time_days = 2.5
                inventory_days_cover = 18.0
                supplier_delay_count = 0
                priority = "2"
                declared_value_usd = 320000.0
            elif any(k in v_up for k in ("CORAL", "LNG", "GAS", "TANKER")):
                material = "Liquefied Natural Gas (LNG) Bulk"
                lead_time_days = 3.5
                inventory_days_cover = 16.0
                supplier_delay_count = 0
                priority = "2"
                declared_value_usd = 680000.0

            dep_calc = now_dt - timedelta(days=max(0, int(lead_time_days * 0.5)))
            eta_calc = now_dt + timedelta(days=max(1, int(lead_time_days * 0.5)))
            departure_date = dep_calc.strftime("%Y-%m-%d")
            eta_date = eta_calc.strftime("%Y-%m-%d")

        # Store in DB
        await asyncio.to_thread(
            self.db.upsert_tracked_vessel,
            imo_number=ident,
            mmsi=m,
            vessel_name=v_name,
            linked_supplier=supplier,
            linked_shipment_id=shipment_id,
            origin=orig,
            destination=dest,
            notes=notes,
            material=material,
            quantity=quantity,
            lead_time_days=lead_time_days,
            inventory_days_cover=inventory_days_cover,
            supplier_delay_count=supplier_delay_count,
            priority=priority,
            declared_value_usd=declared_value_usd,
            departure_date=departure_date,
            eta_date=eta_date,
        )

        # Reload watchlist
        self.load_watchlist()

        # Query live provider immediately
        live_data = await self.provider.get_vessel_by_imo(ident)
        if live_data:
            live_data["imo_number"] = ident
            if m:
                live_data["mmsi"] = m
            if v_name:
                live_data["name"] = v_name
            self._vessel_states[ident] = live_data
            await asyncio.to_thread(self.db.store_position, live_data)
            return self.get_vessel_status(ident) or live_data

        return {
            "imo_number": ident,
            "mmsi": m,
            "name": v_name,
            "status": "active",
            "linked_supplier": supplier,
            "linked_shipment_id": shipment_id,
        }

    def get_realtime_shipments(self) -> list[dict[str, Any]]:
        """Get all active shipments derived dynamically from live tracked vessels."""
        conn = self.db._get_conn()
        cursor = conn.execute("SELECT * FROM tracked_vessels WHERE is_active = 1 ORDER BY id ASC")
        rows = [dict(r) for r in cursor.fetchall()]

        shipments = []
        now = datetime.now(timezone.utc)

        for r in rows:
            imo = str(r.get("imo_number") or "").strip()
            mmsi = str(r.get("mmsi") or "").strip()
            key = imo or mmsi
            if not key:
                continue

            v_status = self.get_vessel_status(key) or {}
            v_name = r.get("vessel_name") or v_status.get("name") or f"Vessel {key}"
            shipment_id = r.get("linked_shipment_id") or f"SHP-{key}"
            supplier = r.get("linked_supplier") or v_name
            origin = r.get("origin") or "Shanghai"
            destination = r.get("destination") or "Rotterdam"
            notes = str(r.get("notes") or "")

            # Dynamic live AIS navigation data
            lat = v_status.get("latitude")
            lon = v_status.get("longitude")
            speed = v_status.get("speed")
            course = v_status.get("course")
            status = v_status.get("status") or "active"
            in_danger = v_status.get("in_danger_zone")

            # Route-aware and vessel-specific logistics attributes
            o_low = origin.lower()
            d_low = destination.lower()
            v_up = v_name.upper()

            # 1. Harbor / Local Gulf Tow (e.g. Houston to Galveston)
            if ("houston" in o_low and "galveston" in d_low) or ("galveston" in o_low and "houston" in d_low) or ("moran" in v_up):
                default_lead = 1.0
                default_mat = "Refined Fuel & Petrochemical Barge Tow"
                default_val = 185000.0
                default_qty = 850.0
                default_inv = 22.0
                default_pri = "1"
                default_delays = 0
                route_nodes = [origin, "Galveston Bay Channel", destination]
                default_progress = 65.0
            # 2. Short European Coastal / Feeder routes (e.g. Rotterdam to Southampton, Antwerp to Felixstowe, Baltic)
            elif (o_low in ("rotterdam", "antwerp", "hamburg", "gdansk", "malmo", "portsmouth") and
                  d_low in ("southampton", "felixstowe", "gothenburg", "stockholm", "kiel", "le havre")):
                default_lead = 2.5
                default_mat = "Containerized Automotive & Industrial Assembly Parts"
                default_val = 320000.0
                default_qty = 1200.0
                default_inv = 18.0
                default_pri = "2"
                default_delays = 0
                route_nodes = [origin, "North Sea Corridor" if "southampton" in d_low or "rotterdam" in o_low else "Channel Feeder Lane", destination]
                default_progress = 55.0
            # 3. Energy / Tanker routes (e.g. LNG or Chemical Tankers)
            elif any(k in v_up for k in ("CORAL", "LNG", "CGAS", "GAS", "TANKER")):
                default_lead = 3.5
                default_mat = "Liquefied Natural Gas (LNG) Bulk" if "CORAL" in v_up or "LNG" in v_up else "High-Purity Chemical Feedstock"
                default_val = 680000.0
                default_qty = 1100.0
                default_inv = 16.0
                default_pri = "2"
                default_delays = 0
                route_nodes = [origin, "North Sea Energy Corridor", destination]
                default_progress = 45.0
            # 4. Long-haul Intercontinental Container mega-vessels
            elif any(k in v_up for k in ("EVER", "MAERSK", "MSC", "COSCO", "CMA CGM", "HMM", "OOCL", "WILSON")):
                is_transpacific = "los angeles" in d_low or "long beach" in d_low
                default_lead = 22.0 if is_transpacific else 26.0
                default_mat = "High-Precision Semiconductor Chips & Electronic Assemblies"
                default_val = 940000.0
                default_qty = 2800.0
                default_delays = 0
                if in_danger or "suez" in notes.lower() or d_low in ("rotterdam", "hamburg", "felixstowe", "antwerp"):
                    route_nodes = [origin, "Singapore", "Suez Canal", destination]
                    # If in danger zone, tight buffer
                    default_inv = 3.5 if in_danger else 14.0
                    default_pri = "3" if in_danger else "2"
                    default_delays = 2 if in_danger else 0
                else:
                    route_nodes = [origin, "Pacific Transit Lane", destination]
                    default_inv = 15.0
                    default_pri = "2"
                default_progress = 52.0
            # 5. Default realistic coastal / regional cargo
            else:
                default_lead = 4.0
                default_mat = "Industrial Supplies & Machinery Feedstock"
                default_val = 350000.0
                default_qty = 1400.0
                default_inv = 17.0
                default_pri = "2"
                default_delays = 0
                route_nodes = [origin, "Coastal Transit Waypoint", destination]
                default_progress = 50.0

            r_mat = str(r.get("material") or "").strip()
            r_lead = float(r.get("lead_time_days") or 0.0)
            if not r_mat or r_mat == "Containerized Cargo" or ("moran" in v_up and r_lead > 2.0):
                mat = default_mat
                lead_days = default_lead
                val = default_val
                qty = default_qty
                inv_days = default_inv
                pri = default_pri
                delays = default_delays
            else:
                lead_days = r_lead if r_lead > 0 else default_lead
                mat = r_mat
                val = float(r.get("declared_value_usd") or default_val)
                qty = float(r.get("quantity") or default_qty)
                inv_days = float(r.get("inventory_days_cover") or default_inv)
                pri = str(r.get("priority") or default_pri)
                delays = int(r.get("supplier_delay_count") if r.get("supplier_delay_count") is not None else default_delays)

            # Dynamic date calculation based on real present time
            dep_dt = now - timedelta(days=max(0, int(lead_days * (default_progress / 100.0))))
            eta_dt = now + timedelta(days=max(1, int(lead_days * ((100.0 - default_progress) / 100.0))))

            v_status_str = status.upper() if status else "UNDERWAY"
            if in_danger:
                v_status_str = f"DANGER ZONE ({in_danger})"

            shipments.append({
                "shipment_id": shipment_id,
                "supplier": supplier,
                "origin": origin,
                "destination": destination,
                "route_nodes": route_nodes,
                "imo_number": imo,
                "mmsi": mmsi,
                "vessel_name": v_name,
                "vessel_latitude": lat if lat is not None else 0.0,
                "vessel_longitude": lon if lon is not None else 0.0,
                "vessel_status": v_status_str,
                "vessel_speed_knots": float(speed) if speed is not None else 12.0,
                "vessel_course_degrees": float(course) if course is not None else 0.0,
                "vessel_progress_percent": default_progress,
                "transport_mode": "sea",
                "material": mat,
                "quantity": qty,
                "lead_time_days": lead_days,
                "inventory_days_cover": inv_days,
                "supplier_delay_count": delays,
                "priority": pri,
                "declared_value_usd": val,
                "departure_date": dep_dt.strftime("%Y-%m-%d"),
                "eta_date": eta_dt.strftime("%Y-%m-%d"),
                "in_danger_zone": in_danger,
            })

        return shipments

    async def remove_tracked_vessel(self, identifier: str) -> bool:
        """Remove a vessel from active tracking."""
        ident = str(identifier).strip()
        success = await asyncio.to_thread(self.db.delete_tracked_vessel, ident)
        self.load_watchlist()
        self._vessel_states.pop(ident, None)
        return success

    async def poll_once(self) -> list[dict[str, Any]]:
        """Perform a single real-time polling cycle for all tracked vessels."""
        watchlist = self.load_watchlist()
        if not watchlist:
            return []

        # Collect all query identifiers (prefer MMSI for VesselAPI if available, else IMO)
        query_ids = []
        entry_map: dict[str, WatchlistEntry] = {}
        for entry in watchlist:
            key = entry.imo_number or entry.mmsi
            query_id = entry.mmsi or entry.imo_number
            query_ids.append(query_id)
            entry_map[query_id] = entry
            entry_map[entry.imo_number] = entry
            if entry.mmsi:
                entry_map[entry.mmsi] = entry

        # Batch query live provider
        updated_vessels = []
        try:
            positions = await self.provider.get_vessels_batch(query_ids)
        except Exception as exc:
            logger.warning("Provider batch fetch error: %s", exc)
            positions = []

        by_mmsi = {str(v.get("mmsi")): v for v in positions if v.get("mmsi")}
        by_imo = {str(v.get("imo_number")): v for v in positions if v.get("imo_number")}

        for entry in watchlist:
            vessel = None
            if entry.mmsi and str(entry.mmsi) in by_mmsi:
                vessel = dict(by_mmsi[str(entry.mmsi)])
            elif entry.imo_number and str(entry.imo_number) in by_imo:
                vessel = dict(by_imo[str(entry.imo_number)])

            if not vessel:
                continue

            # Ensure consistent non-empty identity
            state_key = entry.imo_number or entry.mmsi
            vessel["imo_number"] = state_key
            vessel["mmsi"] = entry.mmsi or vessel.get("mmsi", "")
            vessel["name"] = entry.vessel_name or vessel.get("name") or f"Vessel {state_key}"
            self._vessel_states[state_key] = vessel

            # Store in DB
            await asyncio.to_thread(self.db.store_position, vessel)

            # Check anomalies
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

            # Notify position update
            for callback in self._on_position_update:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(vessel)
                    else:
                        callback(vessel)
                except Exception as e:
                    logger.error(f"Position update callback error: {e}")

            updated_vessels.append(vessel)

        logger.info(f"Live AIS poll complete: {len(updated_vessels)}/{len(watchlist)} vessels updated")
        return updated_vessels

    def _check_anomalies(self, imo: str, vessel: dict[str, Any]) -> list[dict[str, Any]]:
        """Check a vessel for anomalies."""
        anomalies = []
        watchlist_entry = next((w for w in self._watchlist if w.imo_number == imo or w.mmsi == imo), None)
        vessel_name = vessel.get("name") or (watchlist_entry.vessel_name if watchlist_entry else imo)

        # 1. AIS Silence Check
        last_update = vessel.get("last_update")
        if last_update:
            try:
                dt = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                silence_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                if silence_hours >= self.silence_threshold_hours:
                    anomalies.append({
                        "type": "ais_silence",
                        "imo_number": imo,
                        "vessel_name": vessel_name,
                        "severity": "critical" if silence_hours >= 24 else "high",
                        "message": f"AIS signal lost for {vessel_name} — {silence_hours:.1f} hours",
                        "details": f"Last position: {vessel.get('latitude', 0):.4f}N, {vessel.get('longitude', 0):.4f}E",
                        "silence_hours": silence_hours,
                        "linked_supplier": watchlist_entry.linked_supplier if watchlist_entry else "",
                        "linked_shipment_id": watchlist_entry.linked_shipment_id if watchlist_entry else "",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except (ValueError, TypeError):
                pass

        # 2. Speed Anomaly
        current_speed = float(vessel.get("speed") or 0.0)
        speed_history = self._previous_speeds.setdefault(imo, [])
        if len(speed_history) >= 4:
            avg_speed = sum(speed_history[-4:]) / len(speed_history[-4:])
            speed_change = abs(current_speed - avg_speed)
            if speed_change > 8.0 and avg_speed > 2.0 and speed_change > avg_speed * 0.5:
                anomalies.append({
                    "type": "speed_anomaly",
                    "imo_number": imo,
                    "vessel_name": vessel_name,
                    "severity": "medium" if speed_change < 12 else "high",
                    "message": f"Speed anomaly on {vessel_name}: {avg_speed:.1f} → {current_speed:.1f} kts",
                    "details": f"Change of {speed_change:.1f} knots",
                    "current_speed": current_speed,
                    "average_speed": avg_speed,
                    "linked_supplier": watchlist_entry.linked_supplier if watchlist_entry else "",
                    "linked_shipment_id": watchlist_entry.linked_shipment_id if watchlist_entry else "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        speed_history.append(current_speed)
        if len(speed_history) > 10:
            self._previous_speeds[imo] = speed_history[-10:]

        # 3. Danger Zone Check
        lat = float(vessel.get("latitude") or 0.0)
        lon = float(vessel.get("longitude") or 0.0)
        if lat != 0.0 or lon != 0.0:
            for zone in self._danger_zones:
                if (zone["lat_min"] <= lat <= zone["lat_max"] and
                        zone["lon_min"] <= lon <= zone["lon_max"]):
                    anomalies.append({
                        "type": "danger_zone_entry",
                        "imo_number": imo,
                        "vessel_name": vessel_name,
                        "severity": "high" if zone["risk_weight"] >= 25 else "medium",
                        "message": f"{vessel_name} in danger zone: {zone['name']}",
                        "details": f"Position: {lat:.4f}N, {lon:.4f}E | Weight: {zone['risk_weight']}",
                        "zone_name": zone["name"],
                        "risk_weight": zone["risk_weight"],
                        "linked_supplier": watchlist_entry.linked_supplier if watchlist_entry else "",
                        "linked_shipment_id": watchlist_entry.linked_shipment_id if watchlist_entry else "",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    break

        return anomalies

    def get_vessel_status(self, imo: str) -> dict[str, Any] | None:
        """Get current status for a vessel including position and danger zone."""
        vessel = self._vessel_states.get(imo)
        watchlist_entry = next((w for w in self._watchlist if w.imo_number == imo or w.mmsi == imo), None)

        if not vessel:
            # Check latest position in database
            db_pos = self.db.get_latest_position(imo)
            if db_pos:
                vessel = {
                    "imo_number": imo,
                    "mmsi": db_pos.get("mmsi") or (watchlist_entry.mmsi if watchlist_entry else ""),
                    "name": watchlist_entry.vessel_name if watchlist_entry else f"Vessel {imo}",
                    "latitude": float(db_pos.get("lat") or 0.0),
                    "longitude": float(db_pos.get("lon") or 0.0),
                    "speed": float(db_pos.get("speed") or 0.0),
                    "course": float(db_pos.get("course") or 0.0),
                    "heading": float(db_pos.get("heading") or db_pos.get("course") or 0.0),
                    "destination": str(db_pos.get("destination") or (watchlist_entry.destination if watchlist_entry else "")),
                    "nav_status": str(db_pos.get("nav_status") or ""),
                    "last_update": str(db_pos.get("timestamp") or ""),
                }
            elif watchlist_entry:
                vessel = {
                    "imo_number": imo,
                    "mmsi": watchlist_entry.mmsi,
                    "name": watchlist_entry.vessel_name,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "speed": 0.0,
                    "course": 0.0,
                    "heading": 0.0,
                    "destination": watchlist_entry.destination,
                    "last_update": "",
                }
            else:
                return None

        # Determine status
        status = "active"
        last_update = vessel.get("last_update", "")
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                hours_since = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
                if hours_since >= self.silence_threshold_hours:
                    status = "silent"
                elif hours_since >= self.stale_threshold_hours:
                    status = "stale"
            except (ValueError, TypeError):
                pass

        # Danger zone check
        in_danger_zone = None
        lat = float(vessel.get("latitude") or 0.0)
        lon = float(vessel.get("longitude") or 0.0)
        if lat != 0.0 or lon != 0.0:
            for zone in self._danger_zones:
                if (zone["lat_min"] <= lat <= zone["lat_max"] and
                        zone["lon_min"] <= lon <= zone["lon_max"]):
                    in_danger_zone = zone["name"]
                    status = "danger"
                    break

        name = (watchlist_entry.vessel_name if watchlist_entry and watchlist_entry.vessel_name else "") or vessel.get("name") or f"Vessel {imo}"
        return {
            **vessel,
            "name": name,
            "status": status,
            "in_danger_zone": in_danger_zone,
            "linked_supplier": watchlist_entry.linked_supplier if watchlist_entry else None,
            "linked_shipment_id": watchlist_entry.linked_shipment_id if watchlist_entry else None,
            "origin": watchlist_entry.origin if watchlist_entry else None,
            "destination": vessel.get("destination") or (watchlist_entry.destination if watchlist_entry else None),
        }

    def get_fleet_status(self) -> dict[str, Any]:
        """Get summary of fleet status."""
        active = 0
        stale = 0
        silent = 0
        in_danger_zone = 0

        for entry in self._watchlist:
            key = entry.imo_number or entry.mmsi
            status = self.get_vessel_status(key)
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
        """Get status for all tracked vessels."""
        results = []
        for entry in self._watchlist:
            key = entry.imo_number or entry.mmsi
            status = self.get_vessel_status(key)
            if status:
                # Ensure guaranteed valid fields
                status["imo_number"] = key
                results.append(status)
            else:
                results.append({
                    "imo_number": key,
                    "mmsi": entry.mmsi,
                    "name": entry.vessel_name or f"Vessel {key}",
                    "status": "active",
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "speed": 0.0,
                    "course": 0.0,
                    "heading": 0.0,
                    "linked_supplier": entry.linked_supplier,
                    "linked_shipment_id": entry.linked_shipment_id,
                    "destination": entry.destination,
                })
        return results

    def get_danger_zones(self) -> list[dict[str, Any]]:
        """Get danger zone definitions with current vessel counts."""
        zones = []
        for zone in self._danger_zones:
            vessels_inside = []
            for imo, vessel in self._vessel_states.items():
                lat = float(vessel.get("latitude") or 0.0)
                lon = float(vessel.get("longitude") or 0.0)
                if (zone["lat_min"] <= lat <= zone["lat_max"] and
                        zone["lon_min"] <= lon <= zone["lon_max"]):
                    vessels_inside.append(imo)
            zones.append({
                **zone,
                "vessels_inside": vessels_inside,
                "vessel_count": len(vessels_inside),
            })
        return zones
