"""
AISStream.io WebSocket provider for real-time AIS data.
Free, legal real-time AIS data via WebSocket connection.
https://aisstream.io
"""

import asyncio
import json
import logging
import threading
import time
import websockets
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone
from collections import deque

from ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)

# AIS vessel type codes to human-readable names
VESSEL_TYPE_MAP = {
    (20, 29): "Wing in Ground",
    (30, 35): "Fishing",
    (36, 39): "Sailing/Pleasure",
    (40, 49): "High Speed Craft",
    (50, 54): "Special Craft",
    (55, 55): "Military",
    (60, 69): "Passenger",
    (70, 79): "Cargo",
    (80, 89): "Tanker",
    (90, 99): "Other",
}


def classify_vessel_type_code(type_code: int) -> str:
    """Convert AIS type code to human-readable vessel type."""
    for (low, high), name in VESSEL_TYPE_MAP.items():
        if low <= type_code <= high:
            return name
    return "Unknown"


class AISStreamProvider(AISProviderBase):
    """
    Real-time AIS data provider using AISStream.io WebSocket API.
    
    Connects to wss://stream.aisstream.io/v0/stream and receives
    live AIS position reports and static data messages.
    """

    WEBSOCKET_URL = "wss://stream.aisstream.io/v0/stream"

    def __init__(self, api_key: str, bounding_boxes: List[List[List[float]]] = None):
        """
        Initialize AISStream provider.
        
        Args:
            api_key: AISStream.io API key (get free at https://aisstream.io)
            bounding_boxes: Geographic bounds to subscribe to.
                           Default: entire world [[-90, -180], [90, 180]]
        """
        self.api_key = api_key
        self.bounding_boxes = bounding_boxes or [[[-90, -180], [90, 180]]]
        
        # Thread-safe vessel storage
        self._vessels: Dict[str, Dict[str, Any]] = {}
        self._vessel_lock = threading.Lock()
        
        # Connection state
        self._connected = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._message_count = 0
        self._last_message_time: Optional[datetime] = None
        
        # Callbacks for real-time updates
        self._on_vessel_update = None

    def start_streaming(self, on_vessel_update=None):
        """
        Start the WebSocket streaming connection in a background thread.
        
        Args:
            on_vessel_update: Optional callback(vessel_dict) called on each update
        """
        if self._running:
            logger.warning("AISStream already running")
            return
            
        self._on_vessel_update = on_vessel_update
        self._running = True
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()
        logger.info("AISStream WebSocket streaming started")

    def stop_streaming(self):
        """Stop the WebSocket streaming connection."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        self._connected = False
        logger.info("AISStream WebSocket streaming stopped")

    def _run_async_loop(self):
        """Run the asyncio event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._stream_loop())
        except Exception as e:
            logger.error(f"AISStream event loop error: {e}")
        finally:
            self._loop.close()

    async def _stream_loop(self):
        """Main streaming loop with automatic reconnection."""
        while self._running:
            try:
                await self._connect_and_stream()
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"AISStream connection closed: {e}. Reconnecting in 5s...")
                self._connected = False
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"AISStream error: {e}. Reconnecting in 10s...")
                self._connected = False
                await asyncio.sleep(10)

    async def _connect_and_stream(self):
        """Connect to AISStream and process messages."""
        logger.info(f"Connecting to AISStream.io WebSocket...")
        
        async with websockets.connect(self.WEBSOCKET_URL) as websocket:
            # Send subscription message within 3 seconds (required by API)
            subscribe_message = {
                "APIKey": self.api_key,
                "BoundingBoxes": self.bounding_boxes,
                "FilterMessageTypes": ["PositionReport", "ShipStaticData", 
                                       "StandardClassBPositionReport",
                                       "ExtendedClassBPositionReport"]
            }
            await websocket.send(json.dumps(subscribe_message))
            self._connected = True
            logger.info("AISStream connected and subscribed successfully")

            async for message_raw in websocket:
                if not self._running:
                    break
                    
                try:
                    message = json.loads(message_raw)
                    self._process_message(message)
                    self._message_count += 1
                    self._last_message_time = datetime.now(timezone.utc)
                except json.JSONDecodeError:
                    logger.debug("Failed to decode AISStream message")
                except Exception as e:
                    logger.debug(f"Error processing AISStream message: {e}")

    def _process_message(self, message: Dict[str, Any]):
        """Process an incoming AIS message and update vessel data."""
        msg_type = message.get("MessageType", "")
        metadata = message.get("MetaData", {})
        msg_body = message.get("Message", {})

        mmsi = str(metadata.get("MMSI", ""))
        if not mmsi or mmsi == "0":
            return

        with self._vessel_lock:
            # Get or create vessel entry
            vessel = self._vessels.get(mmsi, {
                "mmsi": mmsi,
                "imo": "",
                "name": "",
                "vessel_type": "Unknown",
                "callsign": "",
                "flag": "",
                "length": 0,
                "width": 0,
                "draught": 0,
                "latitude": 0,
                "longitude": 0,
                "course": 0,
                "speed": 0,
                "heading": 0,
                "destination": "",
                "eta": "",
                "nav_status": "",
                "last_update": "",
            })

            # Update from metadata (always available)
            ship_name = metadata.get("ShipName", "").strip()
            if ship_name and ship_name != "Unknown":
                vessel["name"] = ship_name
            
            meta_lat = metadata.get("latitude", 0)
            meta_lon = metadata.get("longitude", 0)
            if meta_lat and meta_lon:
                vessel["latitude"] = float(meta_lat)
                vessel["longitude"] = float(meta_lon)
            
            vessel["last_update"] = metadata.get("time_utc", datetime.now(timezone.utc).isoformat())

            # Process based on message type
            if msg_type == "PositionReport":
                pos = msg_body.get("PositionReport", {})
                vessel["latitude"] = float(pos.get("Latitude", vessel["latitude"]))
                vessel["longitude"] = float(pos.get("Longitude", vessel["longitude"]))
                vessel["speed"] = float(pos.get("Sog", 0))
                vessel["course"] = float(pos.get("Cog", 0)) / 10.0 if pos.get("Cog", 0) > 360 else float(pos.get("Cog", 0))
                vessel["heading"] = float(pos.get("TrueHeading", 0))
                nav_status = pos.get("NavigationalStatus", -1)
                vessel["nav_status"] = self._decode_nav_status(nav_status)

            elif msg_type == "StandardClassBPositionReport":
                pos = msg_body.get("StandardClassBPositionReport", {})
                vessel["latitude"] = float(pos.get("Latitude", vessel["latitude"]))
                vessel["longitude"] = float(pos.get("Longitude", vessel["longitude"]))
                vessel["speed"] = float(pos.get("Sog", 0))
                vessel["course"] = float(pos.get("Cog", 0))
                vessel["heading"] = float(pos.get("TrueHeading", 0))

            elif msg_type == "ExtendedClassBPositionReport":
                pos = msg_body.get("ExtendedClassBPositionReport", {})
                vessel["latitude"] = float(pos.get("Latitude", vessel["latitude"]))
                vessel["longitude"] = float(pos.get("Longitude", vessel["longitude"]))
                vessel["speed"] = float(pos.get("Sog", 0))
                vessel["course"] = float(pos.get("Cog", 0))
                vessel["heading"] = float(pos.get("TrueHeading", 0))
                name = pos.get("Name", "").strip()
                if name:
                    vessel["name"] = name
                vessel["vessel_type"] = classify_vessel_type_code(int(pos.get("Type", 0)))

            elif msg_type == "ShipStaticData":
                static = msg_body.get("ShipStaticData", {})
                name = static.get("Name", "").strip()
                if name:
                    vessel["name"] = name
                vessel["callsign"] = static.get("CallSign", "").strip()
                vessel["imo"] = str(static.get("ImoNumber", "")) if static.get("ImoNumber") else ""
                vessel["vessel_type"] = classify_vessel_type_code(int(static.get("Type", 0)))
                vessel["draught"] = float(static.get("MaximumStaticDraught", 0))
                vessel["destination"] = static.get("Destination", "").strip().replace("@", "")
                
                # Calculate dimensions from A+B (length) and C+D (width)
                dim = static.get("Dimension", {})
                vessel["length"] = float(dim.get("A", 0)) + float(dim.get("B", 0))
                vessel["width"] = float(dim.get("C", 0)) + float(dim.get("D", 0))
                
                # Parse ETA
                eta = static.get("Eta", {})
                if eta and eta.get("Month"):
                    vessel["eta"] = f"{eta.get('Month', 0):02d}-{eta.get('Day', 0):02d} {eta.get('Hour', 0):02d}:{eta.get('Minute', 0):02d}"

            # Filter out invalid positions
            if vessel["latitude"] == 0 and vessel["longitude"] == 0:
                return
            if abs(vessel["latitude"]) > 90 or abs(vessel["longitude"]) > 180:
                return

            self._vessels[mmsi] = vessel

        # Notify callback
        if self._on_vessel_update:
            self._on_vessel_update(vessel)

    def _decode_nav_status(self, status: int) -> str:
        """Decode AIS navigational status code."""
        status_map = {
            0: "Under way using engine",
            1: "At anchor",
            2: "Not under command",
            3: "Restricted manoeuvrability",
            4: "Constrained by draught",
            5: "Moored",
            6: "Aground",
            7: "Engaged in fishing",
            8: "Under way sailing",
            9: "Reserved (HSC)",
            10: "Reserved (WIG)",
            11: "Power-driven towing astern",
            12: "Power-driven pushing/towing",
            14: "AIS-SART active",
            15: "Not defined",
        }
        return status_map.get(status, "Unknown")

    # --- AISProviderBase interface methods ---

    def fetch_vessels(self, bounds: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Return currently tracked vessels from the WebSocket stream.
        
        If streaming hasn't started, this will start it and wait briefly
        for initial data to arrive.
        """
        if not self._running:
            self.start_streaming()
            # Wait up to 10 seconds for initial data
            for _ in range(20):
                time.sleep(0.5)
                with self._vessel_lock:
                    if len(self._vessels) > 0:
                        break

        with self._vessel_lock:
            vessels = list(self._vessels.values())

        if bounds:
            vessels = [
                v for v in vessels
                if bounds.get("lat_min", -90) <= v["latitude"] <= bounds.get("lat_max", 90)
                and bounds.get("lon_min", -180) <= v["longitude"] <= bounds.get("lon_max", 180)
            ]

        logger.info(f"AISStream: returning {len(vessels)} vessels")
        return vessels

    def get_vessel_details(self, mmsi: str) -> Dict[str, Any]:
        """Get details for a specific vessel from the stream cache."""
        with self._vessel_lock:
            return self._vessels.get(mmsi, {})

    def is_available(self) -> bool:
        """Check if the AISStream connection is active."""
        return self._connected

    @property
    def vessel_count(self) -> int:
        """Number of vessels currently being tracked."""
        with self._vessel_lock:
            return len(self._vessels)

    @property
    def message_count(self) -> int:
        """Total messages received since connection."""
        return self._message_count

    @property
    def connected(self) -> bool:
        """Whether the WebSocket is currently connected."""
        return self._connected
