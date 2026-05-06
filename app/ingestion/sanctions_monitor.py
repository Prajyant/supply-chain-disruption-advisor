"""Sanctions monitoring — OFAC SDN List + UN Security Council sanctions.

Free, publicly available data sources:
- OFAC SDN: sanctionssearch.ofac.treas.gov (CSV/XML download)
- UN Sanctions: scsanctions.un.org (XML feed)

Checks vessels, entities, and countries against sanctions lists.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

CACHE_DB_PATH = Path(os.getenv("SANCTIONS_CACHE_DB", "data/sanctions_cache.db"))
CACHE_TTL_HOURS = int(os.getenv("SANCTIONS_CACHE_HOURS", "24"))

# OFAC SDN consolidated list (CSV format)
OFAC_SDN_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
# OFAC consolidated non-SDN (vessels, aircraft)
OFAC_CONSOLIDATED_URL = "https://www.treasury.gov/ofac/downloads/consolidated/cons_prim.csv"
# UN Security Council consolidated list
UN_SANCTIONS_XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"


class SanctionsDatabase:
    """Local SQLite cache of sanctions data for fast lookups."""

    def __init__(self, db_path: Path = CACHE_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sanctioned_entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    entity_type TEXT,
                    source TEXT NOT NULL,
                    country TEXT,
                    program TEXT,
                    vessel_imo TEXT,
                    vessel_mmsi TEXT,
                    remarks TEXT,
                    last_updated TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entity_name
                ON sanctioned_entities(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vessel_imo
                ON sanctioned_entities(vessel_imo)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sanctions_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def needs_refresh(self) -> bool:
        """Check if the sanctions data needs refreshing."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM sanctions_metadata WHERE key = 'last_refresh'"
            ).fetchone()
            if not row:
                return True
            last_refresh = datetime.fromisoformat(row[0])
            return datetime.now(timezone.utc) - last_refresh > timedelta(hours=CACHE_TTL_HOURS)

    def clear_and_reload(self, entities: list[dict[str, Any]], source: str) -> int:
        """Clear existing data for a source and reload."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sanctioned_entities WHERE source = ?", (source,))
            count = 0
            for entity in entities:
                conn.execute(
                    """INSERT INTO sanctioned_entities
                       (name, entity_type, source, country, program, vessel_imo, vessel_mmsi, remarks, last_updated)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entity.get("name", ""),
                        entity.get("entity_type", ""),
                        source,
                        entity.get("country", ""),
                        entity.get("program", ""),
                        entity.get("vessel_imo", ""),
                        entity.get("vessel_mmsi", ""),
                        entity.get("remarks", ""),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                count += 1
            conn.execute(
                """INSERT OR REPLACE INTO sanctions_metadata (key, value)
                   VALUES ('last_refresh', ?)""",
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()
        return count

    def check_entity(self, name: str) -> list[dict[str, Any]]:
        """Check if an entity name matches any sanctioned entity."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT name, entity_type, source, country, program, remarks
                   FROM sanctioned_entities
                   WHERE LOWER(name) LIKE ?""",
                (f"%{name.lower()}%",),
            ).fetchall()
            return [
                {
                    "name": r[0],
                    "entity_type": r[1],
                    "source": r[2],
                    "country": r[3],
                    "program": r[4],
                    "remarks": r[5],
                }
                for r in rows
            ]

    def check_vessel_imo(self, imo_number: str) -> list[dict[str, Any]]:
        """Check if a vessel IMO is sanctioned."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT name, entity_type, source, country, program, remarks
                   FROM sanctioned_entities
                   WHERE vessel_imo = ?""",
                (imo_number,),
            ).fetchall()
            return [
                {
                    "name": r[0],
                    "entity_type": r[1],
                    "source": r[2],
                    "country": r[3],
                    "program": r[4],
                    "remarks": r[5],
                }
                for r in rows
            ]

    def check_country(self, country: str) -> list[dict[str, Any]]:
        """Check sanctions programs active for a country."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT DISTINCT program, source, COUNT(*) as entity_count
                   FROM sanctioned_entities
                   WHERE LOWER(country) LIKE ?
                   GROUP BY program, source""",
                (f"%{country.lower()}%",),
            ).fetchall()
            return [
                {"program": r[0], "source": r[1], "entity_count": r[2]}
                for r in rows
            ]


class OFACClient:
    """Client for downloading and parsing OFAC SDN list."""

    def __init__(self) -> None:
        self.timeout = 30

    def fetch_sdn_list(self) -> list[dict[str, Any]]:
        """Download and parse the OFAC SDN CSV list."""
        entities: list[dict[str, Any]] = []

        try:
            response = requests.get(
                OFAC_SDN_CSV_URL,
                headers={"User-Agent": "Mozilla/5.0 (SupplyChainAdvisor/1.0)"},
                timeout=self.timeout,
            )
            response.raise_for_status()

            reader = csv.reader(io.StringIO(response.text))
            for row in reader:
                if len(row) < 5:
                    continue
                entity = {
                    "name": row[1].strip() if len(row) > 1 else "",
                    "entity_type": row[2].strip() if len(row) > 2 else "",
                    "program": row[3].strip() if len(row) > 3 else "",
                    "country": row[4].strip() if len(row) > 4 else "",
                    "remarks": row[5].strip() if len(row) > 5 else "",
                    "vessel_imo": "",
                    "vessel_mmsi": "",
                }

                # Extract vessel identifiers from remarks
                remarks = entity["remarks"].lower()
                if "imo" in remarks:
                    import re
                    imo_match = re.search(r"imo[:\s]*(\d{7})", remarks)
                    if imo_match:
                        entity["vessel_imo"] = imo_match.group(1)

                if entity["name"]:
                    entities.append(entity)

            logger.info("Parsed %d entities from OFAC SDN list", len(entities))

        except Exception as exc:
            logger.error("Failed to fetch OFAC SDN list: %s", exc)

        return entities


class UNSanctionsClient:
    """Client for UN Security Council consolidated sanctions list."""

    def __init__(self) -> None:
        self.timeout = 30

    def fetch_sanctions_list(self) -> list[dict[str, Any]]:
        """Download and parse the UN consolidated sanctions XML."""
        entities: list[dict[str, Any]] = []

        try:
            response = requests.get(
                UN_SANCTIONS_XML_URL,
                headers={"User-Agent": "Mozilla/5.0 (SupplyChainAdvisor/1.0)"},
                timeout=self.timeout,
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)

            # Parse individuals
            for individual in root.findall(".//INDIVIDUAL"):
                name_parts = []
                for tag in ["FIRST_NAME", "SECOND_NAME", "THIRD_NAME"]:
                    elem = individual.find(tag)
                    if elem is not None and elem.text:
                        name_parts.append(elem.text.strip())

                entities.append({
                    "name": " ".join(name_parts),
                    "entity_type": "individual",
                    "country": self._get_text(individual, "NATIONALITY/VALUE") or "",
                    "program": self._get_text(individual, "UN_LIST_TYPE") or "",
                    "remarks": self._get_text(individual, "COMMENTS1") or "",
                    "vessel_imo": "",
                    "vessel_mmsi": "",
                })

            # Parse entities
            for entity in root.findall(".//ENTITY"):
                name_elem = entity.find("FIRST_NAME")
                name = name_elem.text.strip() if name_elem is not None and name_elem.text else ""

                entities.append({
                    "name": name,
                    "entity_type": "entity",
                    "country": self._get_text(entity, "NATIONALITY/VALUE") or "",
                    "program": self._get_text(entity, "UN_LIST_TYPE") or "",
                    "remarks": self._get_text(entity, "COMMENTS1") or "",
                    "vessel_imo": "",
                    "vessel_mmsi": "",
                })

            logger.info("Parsed %d entities from UN sanctions list", len(entities))

        except Exception as exc:
            logger.error("Failed to fetch UN sanctions list: %s", exc)

        return entities

    def _get_text(self, element: ET.Element, path: str) -> str | None:
        elem = element.find(path)
        return elem.text.strip() if elem is not None and elem.text else None


class SanctionsMonitor:
    """Main sanctions monitoring service.

    Combines OFAC and UN sanctions data for comprehensive screening.
    """

    def __init__(self) -> None:
        self.db = SanctionsDatabase()
        self.ofac = OFACClient()
        self.un = UNSanctionsClient()

    def refresh_if_needed(self) -> dict[str, int]:
        """Refresh sanctions data if cache is stale."""
        if not self.db.needs_refresh():
            logger.debug("Sanctions data is fresh, skipping refresh")
            return {"status": "cached"}

        logger.info("Refreshing sanctions data...")
        stats: dict[str, int] = {}

        # Fetch OFAC
        ofac_entities = self.ofac.fetch_sdn_list()
        if ofac_entities:
            stats["ofac_entities"] = self.db.clear_and_reload(ofac_entities, "ofac")

        # Fetch UN
        un_entities = self.un.fetch_sanctions_list()
        if un_entities:
            stats["un_entities"] = self.db.clear_and_reload(un_entities, "un")

        logger.info("Sanctions refresh complete: %s", stats)
        return stats

    def screen_vessel(self, imo_number: str, vessel_name: str = "") -> dict[str, Any]:
        """Screen a vessel against sanctions lists.

        Returns screening result with match details.
        """
        self.refresh_if_needed()

        matches: list[dict[str, Any]] = []

        # Check by IMO
        if imo_number:
            imo_matches = self.db.check_vessel_imo(imo_number)
            matches.extend(imo_matches)

        # Check by name
        if vessel_name:
            name_matches = self.db.check_entity(vessel_name)
            matches.extend(name_matches)

        is_sanctioned = len(matches) > 0

        return {
            "imo_number": imo_number,
            "vessel_name": vessel_name,
            "is_sanctioned": is_sanctioned,
            "match_count": len(matches),
            "matches": matches[:10],  # Cap at 10 for readability
            "severity": "critical" if is_sanctioned else "low",
            "screened_at": datetime.now(timezone.utc).isoformat(),
        }

    def screen_entity(self, name: str) -> dict[str, Any]:
        """Screen a company/person name against sanctions lists."""
        self.refresh_if_needed()
        matches = self.db.check_entity(name)

        return {
            "entity_name": name,
            "is_sanctioned": len(matches) > 0,
            "match_count": len(matches),
            "matches": matches[:10],
            "severity": "critical" if matches else "low",
            "screened_at": datetime.now(timezone.utc).isoformat(),
        }

    def screen_country_route(self, countries: list[str]) -> dict[str, Any]:
        """Screen a trade route's countries for active sanctions programs."""
        self.refresh_if_needed()
        flagged_countries: list[dict[str, Any]] = []

        for country in countries:
            programs = self.db.check_country(country)
            if programs:
                flagged_countries.append({
                    "country": country,
                    "programs": programs,
                })

        has_sanctions = len(flagged_countries) > 0

        return {
            "countries_checked": countries,
            "flagged_countries": flagged_countries,
            "has_sanctions_exposure": has_sanctions,
            "severity": "high" if has_sanctions else "low",
            "screened_at": datetime.now(timezone.utc).isoformat(),
        }


def normalize_sanctions_event(screening_result: dict[str, Any]) -> dict[str, Any]:
    """Convert sanctions screening result into advisor event format."""
    is_sanctioned = screening_result.get("is_sanctioned", False)
    severity = screening_result.get("severity", "low")
    entity = (
        screening_result.get("vessel_name")
        or screening_result.get("entity_name")
        or screening_result.get("imo_number")
        or "Unknown"
    )

    if is_sanctioned:
        matches = screening_result.get("matches", [])
        match_summary = "; ".join(
            f"{m.get('name', '')} ({m.get('source', '')}/{m.get('program', '')})"
            for m in matches[:3]
        )
        text = (
            f"SANCTIONS ALERT: {entity} matched against sanctions lists. "
            f"Matches: {match_summary}. "
            f"Immediate compliance review required."
        )
    else:
        text = f"Sanctions screening clear for {entity}. No matches found."

    return {
        "source": "sanctions_monitor",
        "reference_id": f"SANCTIONS-{entity}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "supplier": "Compliance",
        "event_time": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "metadata": {
            "title": f"Sanctions screening: {entity} — {severity.upper()}",
            "summary": text,
            "severity": severity,
            "is_sanctioned": is_sanctioned,
            **screening_result,
        },
    }
