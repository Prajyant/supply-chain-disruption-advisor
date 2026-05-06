"""
SQLite database manager for Maritime AI Risk Intelligence Platform.
Handles all persistence: vessels, history, AI reports, alerts, cached routes.
"""

import sqlite3
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Thread-safe SQLite database manager with connection pooling."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path, timeout=30)
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
        return self._local.connection

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS vessels (
                mmsi TEXT PRIMARY KEY,
                imo TEXT,
                name TEXT,
                vessel_type TEXT,
                callsign TEXT,
                flag TEXT,
                length REAL,
                width REAL,
                draught REAL,
                latitude REAL,
                longitude REAL,
                course REAL,
                speed REAL,
                heading REAL,
                destination TEXT,
                eta TEXT,
                nav_status TEXT,
                last_update TEXT,
                risk_score INTEGER DEFAULT 0,
                risk_level TEXT DEFAULT 'LOW',
                last_ai_analysis TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vessel_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mmsi TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                speed REAL,
                course REAL,
                heading REAL,
                risk_score INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mmsi) REFERENCES vessels(mmsi)
            );

            CREATE TABLE IF NOT EXISTS ai_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mmsi TEXT NOT NULL,
                report_json TEXT,
                risk_score INTEGER,
                risk_level TEXT,
                route_analysis TEXT,
                chokepoint_analysis TEXT,
                piracy_threat TEXT,
                weather_concerns TEXT,
                eta_concerns TEXT,
                recommendations TEXT,
                model_used TEXT,
                tokens_used INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mmsi) REFERENCES vessels(mmsi)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mmsi TEXT NOT NULL,
                vessel_name TEXT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT,
                details TEXT,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mmsi) REFERENCES vessels(mmsi)
            );

            CREATE TABLE IF NOT EXISTS cached_routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mmsi TEXT NOT NULL,
                origin TEXT,
                destination TEXT,
                waypoints TEXT,
                distance_nm REAL,
                estimated_duration_hours REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                FOREIGN KEY (mmsi) REFERENCES vessels(mmsi)
            );

            CREATE INDEX IF NOT EXISTS idx_vessel_history_mmsi ON vessel_history(mmsi);
            CREATE INDEX IF NOT EXISTS idx_vessel_history_timestamp ON vessel_history(timestamp);
            CREATE INDEX IF NOT EXISTS idx_ai_reports_mmsi ON ai_reports(mmsi);
            CREATE INDEX IF NOT EXISTS idx_alerts_mmsi ON alerts(mmsi);
            CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
            CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);
        """)
        conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def upsert_vessel(self, vessel_data: Dict[str, Any]):
        conn = self._get_connection()
        now = datetime.utcnow().isoformat()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vessels (mmsi, imo, name, vessel_type, callsign, flag,
                length, width, draught, latitude, longitude, course, speed,
                heading, destination, eta, nav_status, last_update, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mmsi) DO UPDATE SET
                imo=excluded.imo, name=excluded.name, vessel_type=excluded.vessel_type,
                callsign=excluded.callsign, flag=excluded.flag, length=excluded.length,
                width=excluded.width, draught=excluded.draught, latitude=excluded.latitude,
                longitude=excluded.longitude, course=excluded.course, speed=excluded.speed,
                heading=excluded.heading, destination=excluded.destination, eta=excluded.eta,
                nav_status=excluded.nav_status, last_update=excluded.last_update,
                updated_at=excluded.updated_at
        """, (
            vessel_data.get("mmsi"), vessel_data.get("imo"), vessel_data.get("name"),
            vessel_data.get("vessel_type"), vessel_data.get("callsign"), vessel_data.get("flag"),
            vessel_data.get("length"), vessel_data.get("width"), vessel_data.get("draught"),
            vessel_data.get("latitude"), vessel_data.get("longitude"), vessel_data.get("course"),
            vessel_data.get("speed"), vessel_data.get("heading"), vessel_data.get("destination"),
            vessel_data.get("eta"), vessel_data.get("nav_status"), vessel_data.get("last_update"),
            now
        ))
        conn.commit()

    def update_vessel_risk(self, mmsi: str, risk_score: int, risk_level: str):
        conn = self._get_connection()
        conn.execute(
            "UPDATE vessels SET risk_score=?, risk_level=?, updated_at=? WHERE mmsi=?",
            (risk_score, risk_level, datetime.utcnow().isoformat(), mmsi)
        )
        conn.commit()

    def update_vessel_ai_timestamp(self, mmsi: str):
        conn = self._get_connection()
        conn.execute(
            "UPDATE vessels SET last_ai_analysis=?, updated_at=? WHERE mmsi=?",
            (datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), mmsi)
        )
        conn.commit()

    def add_vessel_history(self, mmsi: str, lat: float, lon: float, speed: float,
                           course: float, heading: float, risk_score: int):
        conn = self._get_connection()
        conn.execute("""
            INSERT INTO vessel_history (mmsi, latitude, longitude, speed, course, heading, risk_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (mmsi, lat, lon, speed, course, heading, risk_score))
        conn.commit()

    def add_ai_report(self, mmsi: str, report: Dict[str, Any], model_used: str, tokens_used: int):
        conn = self._get_connection()
        conn.execute("""
            INSERT INTO ai_reports (mmsi, report_json, risk_score, risk_level, route_analysis,
                chokepoint_analysis, piracy_threat, weather_concerns, eta_concerns,
                recommendations, model_used, tokens_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mmsi, json.dumps(report), report.get("risk_score", 0), report.get("risk_level", "LOW"),
            report.get("route_analysis", ""), report.get("chokepoint_analysis", ""),
            report.get("piracy_threat", ""), report.get("weather_concerns", ""),
            report.get("eta_concerns", ""), report.get("recommendations", ""),
            model_used, tokens_used
        ))
        conn.commit()
        self.update_vessel_ai_timestamp(mmsi)

    def add_alert(self, mmsi: str, vessel_name: str, alert_type: str,
                  severity: str, message: str, details: str = ""):
        conn = self._get_connection()
        conn.execute("""
            INSERT INTO alerts (mmsi, vessel_name, alert_type, severity, message, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (mmsi, vessel_name, alert_type, severity, message, details))
        conn.commit()

    def get_all_vessels(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM vessels ORDER BY risk_score DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_vessel(self, mmsi: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM vessels WHERE mmsi=?", (mmsi,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_vessel_history(self, mmsi: str, hours: int = 24) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = conn.execute(
            "SELECT * FROM vessel_history WHERE mmsi=? AND timestamp>=? ORDER BY timestamp",
            (mmsi, since)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_latest_ai_report(self, mmsi: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM ai_reports WHERE mmsi=? ORDER BY created_at DESC LIMIT 1",
            (mmsi,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_unacknowledged_alerts(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM alerts WHERE acknowledged=0 ORDER BY created_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def acknowledge_alert(self, alert_id: int):
        conn = self._get_connection()
        conn.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))
        conn.commit()

    def get_vessels_by_type(self, vessel_type: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM vessels WHERE vessel_type=? ORDER BY risk_score DESC",
            (vessel_type,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_vessels_by_risk(self, risk_level: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM vessels WHERE risk_level=? ORDER BY risk_score DESC",
            (risk_level,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_speed_history(self, mmsi: str, hours: int = 48) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = conn.execute(
            "SELECT speed, timestamp FROM vessel_history WHERE mmsi=? AND timestamp>=? ORDER BY timestamp",
            (mmsi, since)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_risk_trend(self, mmsi: str, hours: int = 48) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = conn.execute(
            "SELECT risk_score, timestamp FROM vessel_history WHERE mmsi=? AND timestamp>=? ORDER BY timestamp",
            (mmsi, since)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_vessel_count_by_region(self) -> Dict[str, int]:
        conn = self._get_connection()
        regions = {
            "Red Sea": (12.0, 30.0, 32.0, 44.0),
            "Gulf of Aden": (10.0, 15.0, 43.0, 54.0),
            "Strait of Hormuz": (24.0, 27.5, 54.0, 58.0),
            "Gulf of Guinea": (-5.0, 8.0, -10.0, 12.0),
            "South China Sea": (0.0, 23.0, 100.0, 121.0),
            "Other": None
        }
        counts = {}
        for name, bounds in regions.items():
            if bounds:
                lat_min, lat_max, lon_min, lon_max = bounds
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM vessels WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
                    (lat_min, lat_max, lon_min, lon_max)
                )
                counts[name] = cursor.fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM vessels").fetchone()[0]
        counts["Other"] = total - sum(counts.values())
        return counts

    def cleanup_old_history(self, days: int = 30):
        conn = self._get_connection()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        conn.execute("DELETE FROM vessel_history WHERE timestamp < ?", (cutoff,))
        conn.execute("DELETE FROM ai_reports WHERE created_at < ?", (cutoff,))
        conn.commit()
        logger.info(f"Cleaned up records older than {days} days")
