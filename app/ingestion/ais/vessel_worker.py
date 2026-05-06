"""
Vessel Tracking Background Worker — integrates AIS engine with the app lifecycle.

Runs as an asyncio background task within the FastAPI lifespan.
Connects vessel anomalies to the risk engine, WebSocket alerts, and playbook system.
"""

import asyncio
import logging
import os
from typing import Any

from app.ingestion.ais.ais_engine import AISEngine, VesselDatabase
from app.ingestion.ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)


def create_ais_provider() -> AISProviderBase:
    """Factory: create the appropriate AIS provider based on configuration.

    Reads AIS_PROVIDER and AIS_API_KEY from environment.
    Falls back to demo mode if no API key is configured or if the key is invalid.
    """
    provider_name = os.getenv("AIS_PROVIDER", "demo").lower()
    api_key = os.getenv("AIS_API_KEY", "").strip()

    if not api_key or provider_name == "demo":
        from app.ingestion.ais.demo_provider import DemoAISProvider
        logger.info("Using Demo AIS provider (no API key configured or demo mode selected)")
        return DemoAISProvider()

    if provider_name == "aisstream":
        from app.ingestion.ais.aisstream_provider import AISStreamProvider
        logger.info("Using AISStream.io real-time WebSocket provider")
        return AISStreamProvider(api_key=api_key)

    if provider_name == "aishub":
        from app.ingestion.ais.aishub_provider import AISHubProvider
        logger.info("Using AISHub AIS provider — will validate key on first poll")
        return AISHubProvider(api_key=api_key)

    if provider_name == "marinetraffic":
        from app.ingestion.ais.marinetraffic_provider import MarineTrafficProvider
        logger.info("Using MarineTraffic AIS provider")
        return MarineTrafficProvider(api_key=api_key)

    # Default to demo
    from app.ingestion.ais.demo_provider import DemoAISProvider
    logger.warning(f"Unknown AIS provider '{provider_name}', falling back to demo")
    return DemoAISProvider()


class VesselTrackingWorker:
    """Background worker that polls AIS data and integrates with the app.

    Integration points:
    - Risk engine: vessel anomalies generate risk events
    - WebSocket: position updates and alerts broadcast to frontend
    - Playbook engine: anomalies can trigger automated playbooks
    - Digital twin graph: linked supplier nodes get risk updates
    - Chat service: vessel fleet status added to global context
    """

    def __init__(self) -> None:
        self._engine: AISEngine | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def engine(self) -> AISEngine | None:
        return self._engine

    def initialize(self) -> AISEngine:
        """Initialize the AIS engine with configured provider and database."""
        provider = create_ais_provider()
        db = VesselDatabase(
            db_path=os.getenv("VESSEL_DB_PATH", "./data/vessel_tracking.db")
        )

        watchlist_path = os.getenv("WATCHLIST_CSV_PATH", "./watchlist.csv")
        poll_interval = int(os.getenv("VESSEL_POLL_INTERVAL_SECONDS", "300"))
        silence_threshold = float(os.getenv("VESSEL_SILENCE_THRESHOLD_HOURS", "6"))
        stale_threshold = float(os.getenv("VESSEL_STALE_THRESHOLD_HOURS", "1"))

        self._engine = AISEngine(
            provider=provider,
            db=db,
            watchlist_path=watchlist_path,
            poll_interval=poll_interval,
            silence_threshold_hours=silence_threshold,
            stale_threshold_hours=stale_threshold,
        )

        # Register anomaly handler
        self._engine.on_anomaly(self._handle_anomaly)
        self._engine.on_position_update(self._handle_position_update)

        # Load watchlist immediately
        entries = self._engine.load_watchlist()

        # If using AISStream provider, pass MMSI watchlist for filtering
        from app.ingestion.ais.aisstream_provider import AISStreamProvider
        if isinstance(provider, AISStreamProvider):
            # Build IMO→MMSI mapping from watchlist CSV and sample CSV
            import csv
            imo_to_mmsi: dict[str, str] = {}
            mmsi_list: list[str] = []
            
            # Read from watchlist.csv (has mmsi column)
            try:
                with open(watchlist_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        imo = (row.get("imo_number") or "").strip()
                        mmsi = (row.get("mmsi") or "").strip()
                        if mmsi:
                            mmsi_list.append(mmsi)
                            if imo:
                                imo_to_mmsi[imo] = mmsi
            except Exception as e:
                logger.warning(f"Could not read MMSI from watchlist: {e}")

            # Also try sample_supplier_upload.csv as fallback
            if not mmsi_list:
                try:
                    with open("./sample_supplier_upload.csv", newline="", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            imo = (row.get("imo_number") or "").strip()
                            mmsi = (row.get("mmsi") or "").strip()
                            if mmsi:
                                mmsi_list.append(mmsi)
                                if imo:
                                    imo_to_mmsi[imo] = mmsi
                except Exception as e:
                    logger.warning(f"Could not read MMSI from sample CSV: {e}")

            if mmsi_list:
                provider.set_watchlist(mmsi_list, imo_to_mmsi)
                logger.info(f"AISStream provider configured with {len(mmsi_list)} MMSI filters")

        logger.info("Vessel tracking worker initialized")
        return self._engine

    async def start(self) -> None:
        """Start the background polling loop."""
        if self._running:
            return
        if not self._engine:
            self.initialize()

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Vessel tracking worker started")

    async def stop(self) -> None:
        """Stop the background polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Close provider
        if self._engine and hasattr(self._engine.provider, "close"):
            await self._engine.provider.close()
        logger.info("Vessel tracking worker stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                updated = await self._engine.poll_once()

                # Fetch marine weather for each vessel's live position
                if updated:
                    await self._fetch_vessel_weather(updated)

                # Purge old positions periodically (every 100 polls)
                retention_days = int(os.getenv("VESSEL_HISTORY_RETENTION_DAYS", "90"))
                await asyncio.to_thread(self._engine.db.purge_old_positions, retention_days)

                # Update chat context with fleet status
                await self._update_chat_context()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Vessel polling error: {e}")

            await asyncio.sleep(self._engine.poll_interval if self._engine else 300)

    async def _fetch_vessel_weather(self, vessels: list[dict[str, Any]]) -> None:
        """Fetch marine weather at each vessel's current position.

        Adds weather data directly to the vessel state so it's available
        via the API and WebSocket broadcasts.
        """
        from app.ingestion.weather_monitor import fetch_open_meteo_marine_weather

        for vessel in vessels:
            lat = vessel.get("latitude")
            lon = vessel.get("longitude")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            if lat == 0 and lon == 0:
                continue

            try:
                weather = await asyncio.to_thread(
                    fetch_open_meteo_marine_weather, lat, lon
                )
                if weather:
                    # Extract from the 'current' nested object
                    current = weather.get("current", {})
                    if not current:
                        current = weather  # fallback if flat structure

                    # Attach weather to the vessel state
                    state_key = vessel.get("imo_number") or vessel.get("mmsi", "")
                    if state_key and state_key in self._engine._vessel_states:
                        self._engine._vessel_states[state_key]["weather"] = {
                            "wave_height": current.get("wave_height"),
                            "wave_direction": current.get("wave_direction"),
                            "wave_period": current.get("wave_period"),
                            "swell_wave_height": current.get("swell_wave_height"),
                            "wind_wave_height": current.get("wind_wave_height"),
                            "ocean_current_velocity": current.get("ocean_current_velocity"),
                            "ocean_current_direction": current.get("ocean_current_direction"),
                            "fetched_at": current.get("time"),
                        }
            except Exception as e:
                logger.debug(f"Weather fetch failed for vessel at {lat},{lon}: {e}")

    async def _handle_anomaly(self, anomaly: dict[str, Any]) -> None:
        """Handle a vessel anomaly — broadcast via WebSocket and create risk event.

        Integration point: connects vessel anomalies to the existing risk/alert pipeline.
        """
        try:
            # Broadcast via WebSocket
            from app.websocket.manager import manager
            await manager.broadcast_alert(
                alert_id=f"vessel-{anomaly['type']}-{anomaly['imo_number']}",
                severity=anomaly.get("severity", "medium"),
                message=anomaly.get("message", "Vessel anomaly detected"),
            )

            # Broadcast vessel-specific update
            await manager._broadcast_to_subscribers(
                manager.all_connections,
                {
                    "type": "vessel_anomaly",
                    "data": anomaly,
                },
            )

            logger.info(
                f"Vessel anomaly broadcast: [{anomaly['severity']}] "
                f"{anomaly['type']} - {anomaly['message']}"
            )

        except Exception as e:
            logger.error(f"Failed to handle vessel anomaly: {e}")

    async def _handle_position_update(self, vessel: dict[str, Any]) -> None:
        """Handle a vessel position update — broadcast via WebSocket."""
        try:
            from app.websocket.manager import manager
            await manager._broadcast_to_subscribers(
                manager.all_connections,
                {
                    "type": "vessel_position_update",
                    "data": {
                        "imo_number": vessel.get("imo_number", ""),
                        "name": vessel.get("name", ""),
                        "latitude": vessel.get("latitude", 0),
                        "longitude": vessel.get("longitude", 0),
                        "speed": vessel.get("speed", 0),
                        "course": vessel.get("course", 0),
                        "status": vessel.get("nav_status", ""),
                    },
                },
            )
        except Exception as e:
            logger.debug(f"Position update broadcast failed: {e}")

    async def _update_chat_context(self) -> None:
        """Push vessel fleet status into the chat service global context."""
        if not self._engine:
            return
        try:
            from app.services.chat_service import ChatService
            chat_service = ChatService()

            fleet_status = self._engine.get_fleet_status()
            all_statuses = self._engine.get_all_vessel_statuses()

            # Add vessel data to the global context
            ctx = chat_service.get_global_context()
            ctx["vessel_fleet_status"] = fleet_status
            ctx["vessel_statuses"] = all_statuses[:20]  # Top 20 for context size

            # Update via the existing method pattern
            chat_service._global_context["vessel_fleet_status"] = fleet_status
            chat_service._global_context["vessel_statuses"] = all_statuses

        except Exception as e:
            logger.debug(f"Chat context update failed: {e}")


# Singleton instance
_vessel_worker: VesselTrackingWorker | None = None


def get_vessel_worker() -> VesselTrackingWorker:
    """Get or create the singleton vessel tracking worker."""
    global _vessel_worker
    if _vessel_worker is None:
        _vessel_worker = VesselTrackingWorker()
    return _vessel_worker
