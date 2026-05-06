"""
AISStream.io WebSocket provider — real-time vessel tracking via free API.

Uses WebSocket connection to wss://stream.aisstream.io/v0/stream
to receive live AIS position reports filtered by MMSI numbers.

Free tier: sign up at https://aisstream.io/ for an API key.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.ingestion.ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)

AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"


class AISStreamProvider(AISProviderBase):
    """AISStream.io WebSocket provider — real-time AIS data.

    Maintains a persistent WebSocket connection that receives position
    reports for vessels matching the configured MMSI filter. Positions
    are cached in memory and served to callers via the standard interface.

    The WebSocket runs as a background task and continuously updates
    the vessel cache. Polling calls return the latest cached position.
    """

    def __init__(self, api_key: str, watchlist_mmsis: list[str] | None = None):
        self.api_key = api_key
        self._watchlist_mmsis: list[str] = watchlist_mmsis or []
        # IMO → latest vessel data
        self._vessel_cache: dict[str, dict[str, Any]] = {}
        # MMSI → latest vessel data (primary key for AIS)
        self._mmsi_cache: dict[str, dict[str, Any]] = {}
        # MMSI → IMO mapping (built from ShipStaticData messages)
        self._mmsi_to_imo: dict[str, str] = {}
        # IMO → MMSI mapping (reverse)
        self._imo_to_mmsi: dict[str, str] = {}
        # WebSocket task
        self._ws_task: asyncio.Task | None = None
        self._connected = False
        self._running = False

    def set_watchlist(self, mmsis: list[str], imo_to_mmsi: dict[str, str] | None = None):
        """Update the MMSI watchlist and IMO mapping.

        Called by the AIS engine when the watchlist is loaded.
        """
        self._watchlist_mmsis = mmsis
        if imo_to_mmsi:
            self._imo_to_mmsi.update(imo_to_mmsi)
            for imo, mmsi in imo_to_mmsi.items():
                self._mmsi_to_imo[mmsi] = imo

    async def start_streaming(self):
        """Start the background WebSocket streaming task."""
        if self._running:
            return
        self._running = True
        self._ws_task = asyncio.create_task(self._stream_loop())
        logger.info("AISStream provider: streaming task started")

    async def stop_streaming(self):
        """Stop the background WebSocket streaming task."""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        logger.info("AISStream provider: streaming task stopped")

    async def _stream_loop(self):
        """Main WebSocket streaming loop with reconnection logic."""
        while self._running:
            try:
                await self._connect_and_stream()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"AISStream WebSocket error: {e}. Reconnecting in 10s...")
                self._connected = False
                await asyncio.sleep(10)

    async def _connect_and_stream(self):
        """Connect to AISStream and process messages."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed. Install with: pip install websockets")
            self._running = False
            return

        logger.info(f"AISStream: Connecting to {AISSTREAM_WS_URL}...")

        try:
            async with websockets.connect(
                AISSTREAM_WS_URL,
                open_timeout=30,
                close_timeout=10,
                ping_interval=20,
                ping_timeout=20,
            ) as ws:
                # Build subscription message
                subscription = {
                    "APIKey": self.api_key,
                    "BoundingBoxes": [[[-90, -180], [90, 180]]],  # Global coverage
                    "FilterMessageTypes": ["PositionReport", "ShipStaticData", "StandardClassBPositionReport"],
                }

                # Add MMSI filter if we have a watchlist (max 50 per AISStream)
                if self._watchlist_mmsis:
                    subscription["FiltersShipMMSI"] = self._watchlist_mmsis[:50]

                await ws.send(json.dumps(subscription))
                self._connected = True
                logger.info(
                    f"AISStream: Connected and subscribed. "
                    f"Filtering {len(self._watchlist_mmsis)} MMSIs"
                )

                async for message_raw in ws:
                    if not self._running:
                        break

                    try:
                        message = json.loads(message_raw)
                        # Check for error messages from AISStream
                        if "error" in message:
                            logger.error(f"AISStream error: {message['error']}")
                            if "not valid" in message.get("error", "").lower():
                                logger.error("AISStream API key is invalid. Stopping.")
                                self._running = False
                                return
                            continue
                        self._process_message(message)
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.debug(f"AISStream message processing error: {e}")
        except Exception as e:
            raise e

    def _process_message(self, message: dict[str, Any]):
        """Process an incoming AIS message and update caches."""
        msg_type = message.get("MessageType", "")
        metadata = message.get("MetaData", {})
        msg_body = message.get("Message", {})

        mmsi = str(metadata.get("MMSI", ""))
        if not mmsi:
            return

        if msg_type == "PositionReport":
            pos = msg_body.get("PositionReport", {})
            self._update_position(mmsi, metadata, pos)
            ship_name = metadata.get("ShipName", "").strip()
            if ship_name:
                logger.info(
                    f"AISStream position: {ship_name} (MMSI {mmsi}) "
                    f"lat={pos.get('Latitude', 0):.4f} lon={pos.get('Longitude', 0):.4f} "
                    f"sog={pos.get('Sog', 0)} cog={pos.get('Cog', 0)}"
                )

        elif msg_type == "StandardClassBPositionReport":
            pos = msg_body.get("StandardClassBPositionReport", {})
            self._update_position(mmsi, metadata, pos)

        elif msg_type == "ShipStaticData":
            static = msg_body.get("ShipStaticData", {})
            self._update_static_data(mmsi, metadata, static)

    def _update_position(self, mmsi: str, metadata: dict, pos: dict):
        """Update vessel position from a PositionReport message."""
        lat = pos.get("Latitude", 0)
        lon = pos.get("Longitude", 0)

        # AIS uses 91 and 181 as "not available" values
        if lat == 91 or lon == 181 or (lat == 0 and lon == 0):
            return

        # AISStream sends Sog and Cog as raw AIS values (already in knots/degrees)
        sog = pos.get("Sog", 0)
        cog = pos.get("Cog", 0)
        # Some messages have Cog in tenths of degrees (>360 means scaled)
        if cog > 360:
            cog = cog / 10.0
        # Some messages have Sog in tenths of knots (>100 means scaled)  
        if sog > 100:
            sog = sog / 10.0

        vessel = self._mmsi_cache.get(mmsi, {})
        vessel.update({
            "mmsi": mmsi,
            "name": metadata.get("ShipName", vessel.get("name", "")).strip(),
            "latitude": lat,
            "longitude": lon,
            "speed": sog,
            "course": cog,
            "heading": pos.get("TrueHeading", 0),
            "nav_status": self._nav_status_text(pos.get("NavigationalStatus", 15)),
            "last_update": metadata.get("time_utc", datetime.now(timezone.utc).isoformat()),
        })

        self._mmsi_cache[mmsi] = vessel

        # Update IMO-indexed cache if we know the mapping
        imo = self._mmsi_to_imo.get(mmsi, vessel.get("imo_number", ""))
        if imo:
            vessel["imo_number"] = imo
            self._vessel_cache[imo] = vessel

    def _update_static_data(self, mmsi: str, metadata: dict, static: dict):
        """Update vessel identity from a ShipStaticData message."""
        imo = str(static.get("ImoNumber", 0))
        if imo and imo != "0":
            self._mmsi_to_imo[mmsi] = imo
            self._imo_to_mmsi[imo] = mmsi

            # Update existing cache entry with IMO
            if mmsi in self._mmsi_cache:
                self._mmsi_cache[mmsi]["imo_number"] = imo
                self._mmsi_cache[mmsi]["name"] = static.get("Name", "").strip() or self._mmsi_cache[mmsi].get("name", "")
                self._mmsi_cache[mmsi]["vessel_type"] = static.get("Type", 0)
                self._mmsi_cache[mmsi]["call_sign"] = static.get("CallSign", "").strip()
                self._mmsi_cache[mmsi]["destination"] = static.get("Destination", "").strip()
                self._vessel_cache[imo] = self._mmsi_cache[mmsi]

    @staticmethod
    def _nav_status_text(code: int) -> str:
        """Convert AIS navigational status code to text."""
        statuses = {
            0: "Under way using engine",
            1: "At anchor",
            2: "Not under command",
            3: "Restricted manoeuvrability",
            4: "Constrained by draught",
            5: "Moored",
            6: "Aground",
            7: "Engaged in fishing",
            8: "Under way sailing",
            9: "Reserved for HSC",
            10: "Reserved for WIG",
            11: "Power-driven vessel towing astern",
            12: "Power-driven vessel pushing ahead",
            14: "AIS-SART",
            15: "Not defined",
        }
        return statuses.get(code, f"Status {code}")

    # ==================== Provider Interface ====================

    async def get_vessel_by_imo(self, imo_number: str) -> dict[str, Any] | None:
        """Get latest cached position for a vessel by IMO."""
        # Start streaming if not already running
        if not self._running:
            await self.start_streaming()
            # Give it a moment to connect and receive initial data
            await asyncio.sleep(3)

        # Direct IMO lookup
        vessel = self._vessel_cache.get(imo_number)
        if vessel:
            return vessel

        # Try via MMSI mapping
        mmsi = self._imo_to_mmsi.get(imo_number)
        if mmsi and mmsi in self._mmsi_cache:
            return self._mmsi_cache[mmsi]

        return None

    async def get_vessel_track(self, imo_number: str, hours: int = 24) -> list[dict[str, Any]]:
        """AISStream doesn't provide historical tracks — returns empty.

        Track history is stored locally in the vessel_positions SQLite table.
        """
        return []

    async def search_vessel(self, query: str) -> list[dict[str, Any]]:
        """Search cached vessels by name."""
        query_lower = query.lower()
        results = []
        for vessel in self._mmsi_cache.values():
            name = vessel.get("name", "")
            if name and query_lower in name.lower():
                results.append(vessel)
        return results[:20]

    async def get_vessels_batch(self, imo_numbers: list[str]) -> list[dict[str, Any]]:
        """Get cached positions for multiple IMOs."""
        # Start streaming if not already running
        if not self._running:
            await self.start_streaming()
            await asyncio.sleep(5)

        results = []
        for imo in imo_numbers:
            vessel = self._vessel_cache.get(imo)
            if vessel:
                results.append(vessel)
            else:
                # Try MMSI lookup
                mmsi = self._imo_to_mmsi.get(imo)
                if mmsi and mmsi in self._mmsi_cache:
                    results.append(self._mmsi_cache[mmsi])
        return results

    async def is_available(self) -> bool:
        """Check if the WebSocket connection is active."""
        return self._connected

    async def close(self) -> None:
        """Stop streaming and clean up."""
        await self.stop_streaming()
