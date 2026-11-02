"""Vessel registry integration — Equasis inspections & detention data.

Equasis (equasis.org) provides free vessel inspection and detention history.
Requires a free account. Rate limited to ~50 queries/day, so we cache aggressively.

Also includes ITU MARS MMSI↔IMO resolution as a fallback identity resolver.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Cache database for vessel registry data
CACHE_DB_PATH = Path(os.getenv("VESSEL_REGISTRY_CACHE_DB", "data/vessel_registry_cache.db"))
CACHE_TTL_DAYS = int(os.getenv("VESSEL_REGISTRY_CACHE_DAYS", "30"))
EQUASIS_DAILY_LIMIT = 50


class VesselRegistryCache:
    """SQLite cache for vessel registry lookups to respect rate limits."""

    def __init__(self, db_path: Path = CACHE_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vessel_registry (
                    imo_number TEXT PRIMARY KEY,
                    data JSON NOT NULL,
                    fetched_at TEXT NOT NULL,
                    source TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_queries (
                    date TEXT PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def get(self, imo_number: str) -> dict[str, Any] | None:
        """Get cached vessel data if still fresh."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data, fetched_at FROM vessel_registry WHERE imo_number = ?",
                (imo_number,),
            ).fetchone()
            if not row:
                return None
            fetched_at = datetime.fromisoformat(row[1])
            if datetime.now(timezone.utc) - fetched_at > timedelta(days=CACHE_TTL_DAYS):
                return None
            return json.loads(row[0])

    def put(self, imo_number: str, data: dict[str, Any], source: str) -> None:
        """Cache vessel registry data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO vessel_registry (imo_number, data, fetched_at, source)
                   VALUES (?, ?, ?, ?)""",
                (imo_number, json.dumps(data), datetime.now(timezone.utc).isoformat(), source),
            )
            conn.commit()

    def can_query_today(self) -> bool:
        """Check if we're under the daily Equasis rate limit."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT count FROM daily_queries WHERE date = ?", (today,)
            ).fetchone()
            return (row[0] if row else 0) < EQUASIS_DAILY_LIMIT

    def increment_daily_count(self) -> None:
        """Increment today's query count."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO daily_queries (date, count) VALUES (?, 1)
                   ON CONFLICT(date) DO UPDATE SET count = count + 1""",
                (today,),
            )
            conn.commit()


class EquasisClient:
    """Client for Equasis vessel inspection/detention data.

    Equasis requires session-based authentication (free account).
    Set EQUASIS_USERNAME and EQUASIS_PASSWORD in .env.
    """

    BASE_URL = "https://www.equasis.org"
    LOGIN_URL = f"{BASE_URL}/EquasisWeb/authen/HomePage?fs=HomePage"
    SEARCH_URL = f"{BASE_URL}/EquasisWeb/restricted/ShipHistory"

    def __init__(self) -> None:
        self.username = os.getenv("EQUASIS_USERNAME", "")
        self.password = os.getenv("EQUASIS_PASSWORD", "")
        self.session: requests.Session | None = None
        self.cache = VesselRegistryCache()

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.password)

    def _login(self) -> bool:
        """Authenticate with Equasis and establish session."""
        if not self.is_configured:
            logger.warning("Equasis credentials not configured")
            return False

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        try:
            # First visit the homepage to get initial cookies
            self.session.get(
                f"{self.BASE_URL}/EquasisWeb/public/HomePage",
                timeout=15,
            )

            # Post login — Equasis uses j_email (not j_username)
            response = self.session.post(
                self.LOGIN_URL,
                data={
                    "j_email": self.username,
                    "j_password": self.password,
                    "submit": "Login",
                },
                timeout=15,
                allow_redirects=True,
            )
            # Equasis may return 404 but still set JSESSIONID on successful login
            if "JSESSIONID" in self.session.cookies.get_dict():
                logger.info("Equasis login successful")
                return True
            logger.warning("Equasis login failed: no session cookie (status=%s)", response.status_code)
            return False
        except Exception as exc:
            logger.error("Equasis login error: %s", exc)
            return False

    def get_vessel_info(self, imo_number: str) -> dict[str, Any] | None:
        """Get vessel inspection and detention data from Equasis.

        Returns cached data if available, otherwise queries Equasis.
        """
        # Check cache first
        cached = self.cache.get(imo_number)
        if cached:
            logger.debug("Equasis cache hit for IMO %s", imo_number)
            return cached

        # Check rate limit
        if not self.cache.can_query_today():
            logger.warning("Equasis daily query limit reached")
            return None

        # Login if needed
        if not self.session and not self._login():
            return None

        try:
            response = self.session.post(
                f"{self.BASE_URL}/EquasisWeb/restricted/ShipInfo?fs=ShipInfo",
                data={"P_IMO": imo_number},
                timeout=20,
                allow_redirects=True,
            )
            response.raise_for_status()
            self.cache.increment_daily_count()

            # Parse the HTML response for key data points
            data = self._parse_vessel_page(response.text, imo_number)
            if data:
                self.cache.put(imo_number, data, "equasis")
            return data

        except Exception as exc:
            logger.error("Equasis query failed for IMO %s: %s", imo_number, exc)
            return None

    def _parse_vessel_page(self, html: str, imo_number: str) -> dict[str, Any] | None:
        """Parse Equasis vessel page HTML for key risk data.

        Extracts: detentions, inspections, classification society, deficiencies.
        """
        import re

        # Strip HTML tags for easier text parsing
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&deg;', '°', text)
        text = re.sub(r'\s+', ' ', text)

        data: dict[str, Any] = {
            "imo_number": imo_number,
            "detentions_last_36_months": 0,
            "inspections_last_36_months": 0,
            "deficiencies_last_36_months": 0,
            "classification_society": None,
            "flag_state": None,
            "ship_type": None,
            "gross_tonnage": None,
            "build_year": None,
            "vessel_name": None,
            "mmsi": None,
            "data_source": "equasis",
        }

        # Extract vessel name (appears as "VESSEL NAME - IMO n° XXXXXXX")
        name_match = re.search(r'Ship\s*info\s+([A-Z][A-Z\s\d]+?)\s*-?\s*IMO', text)
        if name_match:
            data["vessel_name"] = name_match.group(1).strip()

        # Extract flag (appears as "Flag (Country)")
        flag_match = re.search(r'Flag\s*\(([^)]+)\)', text)
        if not flag_match:
            flag_match = re.search(r'Flag\s+([A-Za-z\s]+?)(?:\s+Call)', text)
        if flag_match:
            data["flag_state"] = flag_match.group(1).strip()

        # Extract MMSI
        mmsi_match = re.search(r'MMSI\s+(\d{9})', text)
        if mmsi_match:
            data["mmsi"] = mmsi_match.group(1)

        # Extract gross tonnage
        gt_match = re.search(r'Gross\s*tonnage\s+([\d,]+)', text, re.IGNORECASE)
        if gt_match:
            data["gross_tonnage"] = int(gt_match.group(1).replace(",", ""))

        # Extract ship type
        type_match = re.search(r'Type\s*of\s*ship\s+([A-Za-z\s/]+?)(?:\s*\d|\s*$|\s*Status)', text)
        if type_match:
            data["ship_type"] = type_match.group(1).strip()

        # Extract build year (look for year in "since DD/MM/YYYY" or standalone 4-digit year near build/year)
        year_match = re.search(r'(?:Year\s*of\s*[Bb]uild|[Bb]uilt)\s*:?\s*(\d{4})', text)
        if not year_match:
            # Try to find it from "since DD/MM/YYYY" near tonnage which gives commissioning year
            year_match = re.search(r'since\s+\d{2}/\d{2}/(\d{4})', text)
        if year_match:
            data["build_year"] = int(year_match.group(1))

        # Count detention mentions in the page
        detention_section = re.findall(r'[Dd]etention', html)
        data["detentions_last_36_months"] = max(0, len(detention_section) - 1)  # subtract header mentions

        # Count inspection entries (look for PSC inspection rows)
        inspection_rows = re.findall(r'(?:PSC|Port State|inspection)', html, re.IGNORECASE)
        data["inspections_last_36_months"] = max(0, len(inspection_rows) // 2)

        # Count deficiency mentions
        deficiency_mentions = re.findall(r'[Dd]eficienc', html)
        data["deficiencies_last_36_months"] = max(0, len(deficiency_mentions) - 1)

        # Extract classification society
        class_match = re.search(r'(?:Class(?:ification)?\s*(?:Society)?|[Cc]lass\s*:)\s*([A-Z][A-Za-z\s\']+?)(?:\s*\d|\s*$|\s*Type|\s*Flag)', text)
        if class_match:
            data["classification_society"] = class_match.group(1).strip()

        # If we found at least the vessel name or flag, consider it a valid result
        if data["vessel_name"] or data["flag_state"] or data["gross_tonnage"]:
            return data

        logger.warning("Equasis page for IMO %s didn't contain expected vessel data", imo_number)
        return None


class ITUMARSClient:
    """ITU MARS MMSI ↔ IMO identity resolution.

    Public web interface at itu.int/mmsapp/ShipStation/list.
    No API — web scraping with rate limiting.
    """

    SEARCH_URL = "https://www.itu.int/mmsapp/ShipStation/list"

    def __init__(self) -> None:
        self.cache = VesselRegistryCache()

    def resolve_mmsi_to_imo(self, mmsi: str) -> dict[str, Any] | None:
        """Resolve MMSI to IMO number and vessel identity via ITU MARS."""
        cache_key = f"mmsi-{mmsi}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        try:
            response = requests.get(
                self.SEARCH_URL,
                params={"is498": "false", "mmsi": mmsi},
                headers={"User-Agent": "Mozilla/5.0 (SupplyChainAdvisor/1.0)"},
                timeout=15,
            )
            response.raise_for_status()
            data = self._parse_search_results(response.text, mmsi)
            if data:
                self.cache.put(cache_key, data, "itu_mars")
            return data
        except Exception as exc:
            logger.error("ITU MARS lookup failed for MMSI %s: %s", mmsi, exc)
            return None

    def _parse_search_results(self, html: str, mmsi: str) -> dict[str, Any] | None:
        """Parse ITU MARS search results for vessel identity."""
        import re

        data: dict[str, Any] = {"mmsi": mmsi}

        # Look for IMO number in results
        imo_match = re.search(r"IMO\s*(?:Number)?\s*:?\s*(\d{7})", html, re.IGNORECASE)
        if imo_match:
            data["imo_number"] = imo_match.group(1)

        # Look for vessel name
        name_match = re.search(r"Ship\s*Name\s*:?\s*([^<\n]+)", html, re.IGNORECASE)
        if name_match:
            data["vessel_name"] = name_match.group(1).strip()

        # Look for call sign
        callsign_match = re.search(r"Call\s*Sign\s*:?\s*([A-Z0-9]+)", html, re.IGNORECASE)
        if callsign_match:
            data["call_sign"] = callsign_match.group(1).strip()

        # Look for flag
        flag_match = re.search(r"Flag\s*:?\s*([^<\n]+)", html, re.IGNORECASE)
        if flag_match:
            data["flag"] = flag_match.group(1).strip()

        if "imo_number" not in data and "vessel_name" not in data:
            return None

        return data


def assess_vessel_risk(registry_data: dict[str, Any]) -> dict[str, Any]:
    """Assess vessel risk based on registry data.

    Risk factors:
    - Detentions in last 36 months
    - Vessel age (build year)
    - Number of deficiencies
    - Classification society reputation
    """
    risk_score = 0.0
    risk_factors: list[str] = []

    # Detention risk
    detentions = registry_data.get("detentions_last_36_months", 0)
    if detentions >= 3:
        risk_score += 0.4
        risk_factors.append(f"High detention count: {detentions} in 36 months")
    elif detentions >= 1:
        risk_score += 0.2
        risk_factors.append(f"Detention recorded: {detentions} in 36 months")

    # Age risk
    build_year = registry_data.get("build_year")
    if build_year:
        age = datetime.now().year - build_year
        if age > 25:
            risk_score += 0.3
            risk_factors.append(f"Aged vessel: {age} years old")
        elif age > 20:
            risk_score += 0.15
            risk_factors.append(f"Aging vessel: {age} years old")

    # Deficiency risk
    deficiencies = registry_data.get("deficiencies_last_36_months", 0)
    if deficiencies >= 10:
        risk_score += 0.3
        risk_factors.append(f"High deficiency count: {deficiencies}")
    elif deficiencies >= 5:
        risk_score += 0.15
        risk_factors.append(f"Moderate deficiencies: {deficiencies}")

    # Cap at 1.0
    risk_score = min(risk_score, 1.0)

    # Map to severity
    if risk_score >= 0.7:
        severity = "critical"
    elif risk_score >= 0.5:
        severity = "high"
    elif risk_score >= 0.3:
        severity = "medium"
    else:
        severity = "low"

    return {
        "risk_score": round(risk_score, 2),
        "severity": severity,
        "risk_factors": risk_factors,
        "registry_data": registry_data,
    }


def normalize_registry_event(vessel_risk: dict[str, Any]) -> dict[str, Any]:
    """Convert vessel registry risk assessment into advisor event format."""
    registry = vessel_risk.get("registry_data", {})
    imo = registry.get("imo_number", "unknown")
    severity = vessel_risk.get("severity", "low")
    factors = vessel_risk.get("risk_factors", [])

    text = (
        f"Vessel registry risk assessment for IMO {imo}: "
        f"Severity {severity.upper()}. "
        f"Risk factors: {'; '.join(factors) if factors else 'None identified'}. "
        f"Detentions: {registry.get('detentions_last_36_months', 0)}, "
        f"Deficiencies: {registry.get('deficiencies_last_36_months', 0)}, "
        f"Build year: {registry.get('build_year', 'unknown')}."
    )

    return {
        "source": "vessel_registry",
        "reference_id": f"REGISTRY-{imo}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "supplier": "Vessel Registry",
        "event_time": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "metadata": {
            "title": f"Vessel registry: IMO {imo} — {severity.upper()} risk",
            "summary": text,
            "severity": severity,
            "risk_score": vessel_risk.get("risk_score", 0),
            "risk_factors": factors,
            **registry,
        },
    }
