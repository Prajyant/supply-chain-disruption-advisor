"""WebSocket manager for real-time updates."""
import json
import logging
from typing import Dict, Set, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manager for WebSocket connections and broadcasts."""

    def __init__(self) -> None:
        # Active connections by subscription type
        self.risk_subscribers: Set[WebSocket] = set()
        self.network_subscribers: Set[WebSocket] = set()
        self.alert_subscribers: Set[WebSocket] = set()
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, subscription: str = "all") -> None:
        """Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            subscription: The subscription type ("risks", "network", "alerts", "all")
        """
        await websocket.accept()
        self.all_connections.add(websocket)

        if subscription == "risks" or subscription == "all":
            self.risk_subscribers.add(websocket)
        if subscription == "network" or subscription == "all":
            self.network_subscribers.add(websocket)
        if subscription == "alerts" or subscription == "all":
            self.alert_subscribers.add(websocket)

        logger.info(f"WebSocket connected. Subscription: {subscription}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection
        """
        self.all_connections.discard(websocket)
        self.risk_subscribers.discard(websocket)
        self.network_subscribers.discard(websocket)
        self.alert_subscribers.discard(websocket)
        logger.info("WebSocket disconnected")

    async def broadcast_risk_update(self, risk_id: str, severity: str, node_id: str | None = None) -> None:
        """Broadcast a risk update to all risk subscribers.

        Args:
            risk_id: The risk ID
            severity: The risk severity
            node_id: Optional node ID associated with the risk
        """
        message = {
            "type": "risk_updated",
            "data": {
                "risk_id": risk_id,
                "severity": severity,
                "node_id": node_id,
            },
        }
        await self._broadcast_to_subscribers(self.risk_subscribers, message)

    async def broadcast_node_status(self, node_id: str, status: str, risk_score: float) -> None:
        """Broadcast a node status change to all network subscribers.

        Args:
            node_id: The node ID
            status: The node status
            risk_score: The node's risk score
        """
        message = {
            "type": "node_status_changed",
            "data": {
                "node_id": node_id,
                "status": status,
                "risk_score": risk_score,
            },
        }
        await self._broadcast_to_subscribers(self.network_subscribers, message)

    async def broadcast_alert(self, alert_id: str, severity: str, message: str) -> None:
        """Broadcast a new alert to all alert subscribers.

        Args:
            alert_id: The alert ID
            severity: The alert severity
            message: The alert message
        """
        message = {
            "type": "new_alert",
            "data": {
                "alert_id": alert_id,
                "severity": severity,
                "message": message,
            },
        }
        await self._broadcast_to_subscribers(self.alert_subscribers, message)

    async def broadcast_shipment_update(
        self, shipment_id: str, supplier: str, old_status: str, new_status: str
    ) -> None:
        """Broadcast a shipment status change to all subscribers.

        🔴 CRITICAL FIX #2: This enables real-time Digital Twin updates
        when shipment statuses change from email processing.

        Args:
            shipment_id: The shipment ID
            supplier: The supplier name
            old_status: Previous shipment status
            new_status: New shipment status
        """
        message = {
            "type": "shipment_status_changed",
            "data": {
                "shipment_id": shipment_id,
                "supplier": supplier,
                "old_status": old_status,
                "new_status": new_status,
            },
        }
        await self._broadcast_to_subscribers(self.all_connections, message)

    async def broadcast_playbook_triggered(
        self,
        execution_id: str,
        playbook_name: str,
        node_id: str,
        node_name: str,
        severity: str,
        actions_count: int,
    ) -> None:
        """Broadcast when a playbook auto-triggers.

        ➕ Demo: Shows real-time toast on Dashboard — the '80% manual
        oversight reduction' made visible.

        Args:
            execution_id: The execution ID
            playbook_name: Name of the triggered playbook
            node_id: The affected node ID
            node_name: The affected node name
            severity: The risk severity
            actions_count: Number of action steps
        """
        message = {
            "type": "playbook_triggered",
            "data": {
                "execution_id": execution_id,
                "playbook_name": playbook_name,
                "node_id": node_id,
                "node_name": node_name,
                "severity": severity,
                "actions_count": actions_count,
            },
        }
        await self._broadcast_to_subscribers(self.all_connections, message)

    async def broadcast_ingestion_complete(self, events_count: int, risks_count: int) -> None:
        """Broadcast ingestion completion to all subscribers.

        Args:
            events_count: Number of events ingested
            risks_count: Number of risks detected
        """
        message = {
            "type": "ingestion_complete",
            "data": {
                "events_count": events_count,
                "risks_count": risks_count,
            },
        }
        await self._broadcast_to_subscribers(self.all_connections, message)

    async def _broadcast_to_subscribers(self, subscribers: Set[WebSocket], message: Dict[str, Any]) -> None:
        """Broadcast a message to a set of subscribers.

        Args:
            subscribers: Set of WebSocket connections
            message: The message to broadcast
        """
        disconnected = set()
        for connection in subscribers:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager instance
manager = ConnectionManager()
