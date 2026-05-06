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
    LOGIN_URL = f"{BASE_URL}/EquasisWeb/authen/HomePage"
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
            "User-Agent": "Mozilla/5.0 (SupplyChainAdvisor/1.0)"
        })

        try:
            response = self.session.post(
                self.LOGIN_URL,
                data={
                    "j_username": self.username,
                    "j_password": self.password,
                    "submit": "Login",
                },
                timeout=15,
            )
            if response.status_code == 200 and "JSESSIONID" in self.session.cookies.get_dict():
                logger.info("Equasis login successful")
                return True
            logger.warning("Equasis login failed: status=%s", response.status_code)
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
            response = self.session.get(
                self.SEARCH_URL,
                params={"IMO": imo_number},
                timeout=15,
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
            "detention_details": [],
        }

        # Extract detention count
        detention_match = re.search(
            r"Detentions?\s*(?:in last 36 months)?\s*:\s*(\d+)", html, re.IGNORECASE
        )
        if detention_match:
            data["detentions_last_36_months"] = int(detention_match.group(1))

        # Extract inspection count
        inspection_match = re.search(
            r"Inspections?\s*(?:in last 36 months)?\s*:\s*(\d+)", html, re.IGNORECASE
        )
        if inspection_match:
            data["inspections_last_36_months"] = int(inspection_match.group(1))

        # Extract deficiency count
        deficiency_match = re.search(
            r"Deficienc(?:y|ies)\s*:\s*(\d+)", html, re.IGNORECASE
        )
        if deficiency_match:
            data["deficiencies_last_36_months"] = int(deficiency_match.group(1))

        # Extract classification society
        class_match = re.search(
            r"Classification\s*(?:Society)?\s*:\s*([^<\n]+)", html, re.IGNORECASE
        )
        if class_match:
            data["classification_society"] = class_match.group(1).strip()

        # Extract build year
        year_match = re.search(r"Year\s*(?:of)?\s*Build\s*:\s*(\d{4})", html, re.IGNORECASE)
        if year_match:
            data["build_year"] = int(year_match.group(1))

        # Extract flag
        flag_match = re.search(r"Flag\s*:\s*([^<\n]+)", html, re.IGNORECASE)
        if flag_match:
            data["flag_state"] = flag_match.group(1).strip()

        # Extract gross tonnage
        gt_match = re.search(r"Gross\s*Tonnage\s*:\s*([\d,]+)", html, re.IGNORECASE)
        if gt_match:
            data["gross_tonnage"] = int(gt_match.group(1).replace(",", ""))

        return data


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
