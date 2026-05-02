"""Graph service for digital twin visualization and impact propagation."""
import logging
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    """Node types in the supply chain graph."""
    SUPPLIER = "supplier"
    WAREHOUSE = "warehouse"
    PLANT = "plant"


class EdgeType(str, Enum):
    """Edge types in the supply chain graph."""
    SUPPLIES_TO = "supplies_to"
    SHIPS_TO = "ships_to"


class NodeStatus(str, Enum):
    """Node status values."""
    NORMAL = "normal"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass
class Node:
    """A node in the supply chain graph."""
    id: str
    type: NodeType
    name: str
    location: str
    risk_score: float = 0.0
    status: NodeStatus = NodeStatus.NORMAL
    criticality: str = "medium"
    direct_risk: float = 0.0
    derived_risk: float = 0.0

    @property
    def final_risk(self) -> float:
        """Get the final risk score (max of direct and derived)."""
        return max(self.direct_risk, self.derived_risk)


@dataclass
class Edge:
    """An edge in the supply chain graph."""
    from_node: str
    to_node: str
    type: EdgeType
    material_type: str = ""
    volume: float = 0.0
    lead_time: int = 0
    _weight: float = 0.5

    @property
    def weight(self) -> float:
        """Calculate edge weight based on volume and criticality."""
        # Weight ranges from 0.1 to 1.0 based on volume
        return self._weight if self._weight > 0 else min(1.0, max(0.1, self.volume / 10000.0))

    @weight.setter
    def weight(self, value: float) -> None:
        """Set edge weight directly."""
        self._weight = value

    def __post_init__(self) -> None:
        """Initialize weight after dataclass creation."""
        if self._weight == 0.5 and self.volume > 0:
            self._weight = min(1.0, max(0.1, self.volume / 10000.0))


@dataclass
class SupplyChainGraph:
    """The supply chain graph containing nodes and edges."""
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    last_updated: Optional[str] = None

    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_upstream_nodes(self, node_id: str) -> list[Node]:
        """Get all nodes that supply to this node."""
        return [
            self.nodes[edge.from_node]
            for edge in self.edges
            if edge.to_node == node_id and edge.from_node in self.nodes
        ]

    def get_downstream_nodes(self, node_id: str) -> list[Node]:
        """Get all nodes that this node supplies to."""
        return [
            self.nodes[edge.to_node]
            for edge in self.edges
            if edge.from_node == node_id and edge.to_node in self.nodes
        ]


class GraphService:
    """Service for managing the supply chain digital twin."""
    def __init__(self) -> None:
        """Initialize the graph service."""
        self.graph = SupplyChainGraph()
        self.propagation_factor = 0.3
        self.propagation_threshold = 0.6
        self._context_summary_cache: dict[str, dict] = {}

    def load_sample_graph(self) -> None:
        """Load the supply chain graph from the demo shipments CSV.

        Builds a focused graph: suppliers → key transit hubs → destinations.
        Skips generic ocean waypoints to keep the graph readable.
        """
        if self.graph.nodes:
            return

        import csv
        import re
        from datetime import datetime, timezone
        from pathlib import Path

        csv_path = Path("frontend/public/demo_shipments.csv")
        if not csv_path.exists():
            logger.warning("demo_shipments.csv not found, using minimal fallback graph")
            self._load_minimal_fallback()
            return

        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                shipments = list(csv.DictReader(f))
        except Exception as exc:
            logger.error("Failed to read demo_shipments.csv: %s", exc)
            self._load_minimal_fallback()
            return

        def make_id(prefix: str, name: str) -> str:
            return prefix + "_" + re.sub(r"[^a-z0-9]", "_", name.lower().strip())[:30]

        # Skip generic ocean/transit waypoints — they add clutter without value
        SKIP_WAYPOINTS = {
            "pacific ocean", "north atlantic", "st louis", "windsor",
            "nuremberg",
        }

        # Key transit chokepoints worth showing
        TRANSIT_HUBS = {
            "suez canal", "gibraltar", "hormuz", "singapore",
        }

        # Final inland destinations
        DESTINATIONS = {
            "memphis", "frankfurt", "dallas", "detroit", "chicago", "munich",
            "hamburg", "newark", "los angeles", "ningbo", "rotterdam",
        }

        nodes_map: dict[str, Node] = {}
        edge_set: set[tuple[str, str, str]] = set()
        shipment_counts: dict[str, int] = {}

        for row in shipments:
            supplier = row.get("supplier", "").strip()
            origin = row.get("origin", "").strip()
            destination = row.get("destination", "").strip()
            route_str = row.get("route_nodes", "")
            material = row.get("material", "").strip()

            if not origin or not destination:
                continue

            raw_route = [n.strip() for n in route_str.split("|") if n.strip()] if route_str else [origin, destination]

            # Filter route to: origin → transit hubs → destination
            filtered_route = []
            for loc in raw_route:
                lower = loc.lower().strip()
                if lower in SKIP_WAYPOINTS:
                    continue
                filtered_route.append(loc)

            if not filtered_route:
                filtered_route = [origin, destination]

            # Ensure origin and destination are in the route
            if filtered_route[0].lower() != origin.lower():
                filtered_route.insert(0, origin)
            if filtered_route[-1].lower() != destination.lower():
                filtered_route.append(destination)

            # Create supplier node (represents the supplier at their origin)
            if supplier:
                sid = make_id("sup", supplier)
                if sid not in nodes_map:
                    nodes_map[sid] = Node(
                        id=sid, type=NodeType.SUPPLIER,
                        name=supplier, location=origin, criticality="medium",
                    )
                shipment_counts[sid] = shipment_counts.get(sid, 0) + 1

            # Create location nodes — skip origin if supplier already covers it
            for loc in filtered_route:
                lid = make_id("loc", loc)
                lower = loc.lower().strip()

                # Skip creating a separate origin node if the supplier is at this location
                if supplier and lower == origin.lower().strip():
                    continue

                if lid not in nodes_map:
                    if lower in TRANSIT_HUBS:
                        ntype = NodeType.WAREHOUSE
                    elif lower in DESTINATIONS:
                        ntype = NodeType.PLANT
                    else:
                        ntype = NodeType.SUPPLIER
                    nodes_map[lid] = Node(
                        id=lid, type=ntype,
                        name=loc, location=loc, criticality="medium",
                    )
                shipment_counts[lid] = shipment_counts.get(lid, 0) + 1

            # Edges: supplier → first non-origin route node (or second node)
            if supplier:
                sid = make_id("sup", supplier)
                # Find the first route node that isn't the origin
                target_nodes = [n for n in filtered_route if n.lower().strip() != origin.lower().strip()]
                if target_nodes:
                    first_lid = make_id("loc", target_nodes[0])
                    if sid != first_lid:
                        edge_set.add((sid, first_lid, material))
                elif len(filtered_route) >= 2:
                    # Origin == first route node, connect to second
                    first_lid = make_id("loc", filtered_route[1])
                    if sid != first_lid:
                        edge_set.add((sid, first_lid, material))

            # Edges: along the route (skip origin since supplier covers it)
            route_ids = []
            for loc in filtered_route:
                if supplier and loc.lower().strip() == origin.lower().strip():
                    route_ids.append(make_id("sup", supplier))
                else:
                    route_ids.append(make_id("loc", loc))

            for i in range(len(route_ids) - 1):
                fid = route_ids[i]
                tid = route_ids[i + 1]
                if fid != tid:
                    edge_set.add((fid, tid, material))

        # Set criticality
        for nid, count in shipment_counts.items():
            node = nodes_map.get(nid)
            if node:
                node.criticality = "high" if count >= 3 else "medium" if count >= 2 else "low"

        # Add to graph
        for node in nodes_map.values():
            self.graph.add_node(node)
        for from_id, to_id, mat in edge_set:
            self.graph.add_edge(Edge(from_id, to_id, EdgeType.SUPPLIES_TO, mat, volume=1000, lead_time=7))

        self.graph.last_updated = datetime.now(timezone.utc).isoformat()
        logger.info(
            "Digital Twin built from CSV: %d nodes, %d edges from %d shipments",
            len(self.graph.nodes), len(self.graph.edges), len(shipments),
        )

        # Score nodes immediately from shipment data (no external API calls needed)
        self._score_nodes_from_shipments(shipments)
        self.propagate_risk()

    def _score_nodes_from_shipments(self, shipments: list[dict]) -> None:
        """Score graph nodes using shipment risk factors from the CSV.

        This runs at startup without any external API calls. It uses:
        - Inventory pressure (low days_cover = high risk)
        - Supplier delay history
        - Vessel status (moored/anchored/waiting = higher risk)
        - Lead time (longer = more exposure)
        - Priority (higher priority = more impact)
        """
        import re

        def make_id(prefix: str, name: str) -> str:
            return prefix + "_" + re.sub(r"[^a-z0-9]", "_", name.lower().strip())[:30]

        # Accumulate max risk per node from all shipments passing through it
        node_risks: dict[str, float] = {}

        for row in shipments:
            supplier = row.get("supplier", "").strip()
            origin = row.get("origin", "").strip()
            destination = row.get("destination", "").strip()
            route_str = row.get("route_nodes", "")

            # Calculate shipment risk score (0.0 to 1.0)
            inventory = float(row.get("inventory_days_cover", 30) or 30)
            delays = int(row.get("supplier_delay_count", 0) or 0)
            lead_time = int(row.get("lead_time_days", 0) or 0)
            priority = int(row.get("priority", 0) or 0)
            vessel_status = row.get("vessel_status", "").lower()

            risk = 0.0
            # Inventory pressure
            if inventory <= 2:
                risk += 0.35
            elif inventory <= 5:
                risk += 0.2
            elif inventory <= 10:
                risk += 0.1

            # Supplier delays
            risk += min(delays * 0.08, 0.25)

            # Lead time exposure
            if lead_time >= 20:
                risk += 0.15
            elif lead_time >= 10:
                risk += 0.08

            # Priority
            if priority >= 3:
                risk += 0.1
            elif priority >= 2:
                risk += 0.05

            # Vessel status
            if any(s in vessel_status for s in ["moored", "waiting", "anchored"]):
                risk += 0.15
            elif "underway" not in vessel_status and vessel_status:
                risk += 0.1

            risk = min(risk, 0.95)

            # Apply risk to all nodes on this shipment's route
            route_nodes = [n.strip() for n in route_str.split("|") if n.strip()] if route_str else []
            affected_ids = set()

            if supplier:
                affected_ids.add(make_id("sup", supplier))
            for loc in route_nodes:
                affected_ids.add(make_id("loc", loc))
            if destination:
                affected_ids.add(make_id("loc", destination))

            for nid in affected_ids:
                node_risks[nid] = max(node_risks.get(nid, 0.0), risk)

        # Apply scores to graph nodes
        scored = 0
        for nid, risk in node_risks.items():
            node = self.graph.get_node(nid)
            if node and risk > node.direct_risk:
                node.direct_risk = risk
                scored += 1

        logger.info("Scored %d graph nodes from shipment data", scored)

    def _load_minimal_fallback(self) -> None:
        """Minimal fallback graph when CSV is unavailable."""
        from datetime import datetime, timezone
        self.graph.add_node(Node("fallback_origin", NodeType.SUPPLIER, "Origin Port", "Unknown"))
        self.graph.add_node(Node("fallback_dest", NodeType.PLANT, "Destination", "Unknown"))
        self.graph.add_edge(Edge("fallback_origin", "fallback_dest", EdgeType.SHIPS_TO, "cargo"))
        self.graph.last_updated = datetime.now(timezone.utc).isoformat()

    def get_network(self) -> dict:
        """Get the full network graph.

        Returns:
            Dictionary with nodes, edges, and metadata
        """
        return {
            "nodes": [
                {
                    "id": node.id,
                    "type": node.type.value,
                    "name": node.name,
                    "location": node.location,
                    "risk_score": node.final_risk,
                    "status": node.status.value,
                    "criticality": node.criticality,
                    "context_summary": self._context_summary_cache.get(node.id, {
                        "shipment_count": 0, "order_count": 0,
                        "risk_count": 0, "has_critical_risk": False,
                    }),
                }
                for node in self.graph.nodes.values()
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "type": edge.type.value,
                    "material_type": edge.material_type,
                    "volume": edge.volume,
                    "lead_time": edge.lead_time,
                }
                for edge in self.graph.edges
            ],
            "metadata": {
                "last_updated": self.graph.last_updated,
                "total_risks": sum(1 for n in self.graph.nodes.values() if n.final_risk > 0.5),
            },
        }

    def get_node(self, node_id: str) -> Optional[dict]:
        """Get details for a specific node.

        Args:
            node_id: The node ID

        Returns:
            Node details dictionary or None
        """
        node = self.graph.get_node(node_id)
        if not node:
            return None

        return {
            "id": node.id,
            "type": node.type.value,
            "name": node.name,
            "location": node.location,
            "risk_score": node.final_risk,
            "direct_risk": node.direct_risk,
            "derived_risk": node.derived_risk,
            "status": node.status.value,
            "criticality": node.criticality,
        }

    def get_node_impact(self, node_id: str) -> dict:
        """Get upstream and downstream impact for a node.

        Args:
            node_id: The node ID

        Returns:
            Dictionary with upstream and downstream nodes
        """
        upstream = self.graph.get_upstream_nodes(node_id)
        downstream = self.graph.get_downstream_nodes(node_id)

        return {
            "node_id": node_id,
            "upstream": [
                {
                    "id": n.id,
                    "name": n.name,
                    "type": n.type.value,
                    "risk_score": n.final_risk,
                    "status": n.status.value,
                }
                for n in upstream
            ],
            "downstream": [
                {
                    "id": n.id,
                    "name": n.name,
                    "type": n.type.value,
                    "risk_score": n.final_risk,
                    "status": n.status.value,
                }
                for n in downstream
            ],
        }

    def propagate_risk(self) -> dict:
        """Propagate risk scores through the graph.

        Returns:
            Dictionary with propagation results
        """
        # Reset derived risks
        for node in self.graph.nodes.values():
            node.derived_risk = 0.0

        # Propagate risk through edges
        for edge in self.graph.edges:
            from_node = self.graph.get_node(edge.from_node)
            to_node = self.graph.get_node(edge.to_node)

            if from_node and to_node:
                if from_node.final_risk > self.propagation_threshold:
                    risk_transfer = (
                        from_node.final_risk
                        * edge.weight
                        * self.propagation_factor
                    )
                    to_node.derived_risk += risk_transfer

        # Update node statuses based on final risk
        updated_nodes = []
        for node in self.graph.nodes.values():
            old_status = node.status
            final_risk = node.final_risk

            if final_risk >= 0.8:
                node.status = NodeStatus.CRITICAL
            elif final_risk >= 0.6:
                node.status = NodeStatus.AT_RISK
            else:
                node.status = NodeStatus.NORMAL

            if old_status != node.status:
                updated_nodes.append(node.id)

        self.graph.last_updated = "2026-04-24T10:30:00Z"

        return {
            "propagated": True,
            "updated_nodes": updated_nodes,
            "total_risks": sum(1 for n in self.graph.nodes.values() if n.final_risk > 0.5),
        }

    def set_node_direct_risk(self, node_id: str, risk_score: float) -> bool:
        """Set the direct risk score for a node.

        Args:
            node_id: The node ID
            risk_score: The direct risk score (0.0 to 1.0)

        Returns:
            True if successful, False if node not found
        """
        node = self.graph.get_node(node_id)
        if not node:
            return False

        node.direct_risk = max(0.0, min(1.0, risk_score))
        return True

    def add_or_update_node(self, supplier_name: str, risk_score: float) -> str:
        """Dynamically create or update a supplier node from a live event.

        If a node for this supplier already exists, its risk score is updated.
        If not, a brand-new node is added to the Digital Twin map.

        Args:
            supplier_name: Human-readable supplier / sender name
            risk_score: Direct risk score (0.0 to 1.0)

        Returns:
            The node ID that was created or updated
        """
        import re
        from datetime import datetime, timezone

        # Build a stable node ID from the supplier name
        node_id = "live_" + re.sub(r"[^a-z0-9]", "_", supplier_name.lower())[:30]

        node = self.graph.get_node(node_id)
        if node is None:
            node = Node(
                id=node_id,
                type=NodeType.SUPPLIER,
                name=supplier_name,
                location="Live Email Source",
                criticality="medium",
            )
            self.graph.add_node(node)

        node.direct_risk = max(0.0, min(1.0, risk_score))
        self.graph.last_updated = datetime.now(timezone.utc).isoformat()
        return node_id

    def update_context_summary(
        self, node_id: str, shipment_count: int = 0,
        order_count: int = 0, risk_count: int = 0,
        has_critical_risk: bool = False,
    ) -> None:
        """Update the lightweight context summary cache for a node.

        Called at ingest time — NOT inside get_network().
        """
        self._context_summary_cache[node_id] = {
            "shipment_count": shipment_count,
            "order_count": order_count,
            "risk_count": risk_count,
            "has_critical_risk": has_critical_risk,
        }

    def get_node_context(self, node_id: str) -> Optional[dict]:
        """Get full enriched context for a node (called on node click only).

        Returns the complete 'knowledge card' with shipments, risk data,
        news, and upstream/downstream impact. Pulls data directly from
        the shipments CSV and live intelligence.
        """
        node = self.graph.get_node(node_id)
        if not node:
            return None

        upstream = self.graph.get_upstream_nodes(node_id)
        downstream = self.graph.get_downstream_nodes(node_id)

        # Find shipments that pass through this node
        active_shipments = self._find_shipments_for_node(node)

        # Find weather/trade/news events relevant to this node's location
        connected_news = self._find_news_for_node(node)

        # Build risk history from weather/trade intelligence
        risk_history = self._find_risks_for_node(node)

        return {
            "id": node.id,
            "type": node.type.value,
            "name": node.name,
            "location": node.location,
            "risk_score": node.final_risk,
            "direct_risk": node.direct_risk,
            "derived_risk": node.derived_risk,
            "status": node.status.value,
            "criticality": node.criticality,
            "financial_exposure_usd": None,
            "days_buffer": None,
            "active_shipments": active_shipments,
            "pending_orders": [],
            "risk_history": risk_history,
            "connected_news": connected_news,
            "upstream_nodes": [
                {"id": n.id, "name": n.name, "type": n.type.value,
                 "risk_score": n.final_risk, "status": n.status.value,
                 "location": n.location, "criticality": n.criticality}
                for n in upstream
            ],
            "downstream_nodes": [
                {"id": n.id, "name": n.name, "type": n.type.value,
                 "risk_score": n.final_risk, "status": n.status.value,
                 "location": n.location, "criticality": n.criticality}
                for n in downstream
            ],
            "context_summary": self._context_summary_cache.get(node_id, {
                "shipment_count": len(active_shipments),
                "order_count": 0,
                "risk_count": len(risk_history),
                "has_critical_risk": node.final_risk >= 0.8,
            }),
        }

    def _find_shipments_for_node(self, node: Node) -> list[dict]:
        """Find shipments from the CSV that pass through this node."""
        import csv
        from pathlib import Path

        csv_path = Path("frontend/public/demo_shipments.csv")
        if not csv_path.exists():
            return []

        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                shipments = list(csv.DictReader(f))
        except Exception:
            return []

        node_lower = node.name.lower().strip()
        results = []

        for row in shipments:
            supplier = row.get("supplier", "").lower().strip()
            origin = row.get("origin", "").lower().strip()
            destination = row.get("destination", "").lower().strip()
            route_str = row.get("route_nodes", "").lower()

            # Check if this node is on the shipment's route
            if (node_lower == supplier or node_lower == origin or
                node_lower == destination or node_lower in route_str):
                status = "in_transit"
                vessel_status = row.get("vessel_status", "").lower()
                if "moored" in vessel_status or "waiting" in vessel_status:
                    status = "delayed"
                elif "anchored" in vessel_status:
                    status = "delayed"

                results.append({
                    "shipment_id": row.get("shipment_id", ""),
                    "supplier": row.get("supplier", ""),
                    "material": row.get("material", ""),
                    "status": status,
                    "eta_days": int(row.get("lead_time_days", 0) or 0),
                    "origin": row.get("origin", ""),
                    "destination": row.get("destination", ""),
                    "tracking_number": row.get("imo_number", ""),
                    "departure_date": row.get("departure_date", ""),
                    "last_updated": row.get("eta_date", ""),
                })

        return results

    def _find_news_for_node(self, node: Node) -> list[dict]:
        """Find news/trade events relevant to this node's location."""
        from app.ingestion.weather_monitor import fetch_weather_events
        from app.ingestion.trade_monitor import fetch_trade_policy_events

        node_lower = node.name.lower()
        node_loc_lower = node.location.lower()
        results = []

        try:
            for event in fetch_weather_events(limit=10):
                meta = event.get("metadata", {})
                loc = str(meta.get("location", "")).lower()
                if loc and (loc in node_lower or node_lower in loc or loc in node_loc_lower):
                    results.append({
                        "news_id": event.get("reference_id", ""),
                        "headline": meta.get("title", ""),
                        "region": meta.get("country", ""),
                        "date": event.get("event_time", ""),
                        "relevance_score": 0.9,
                    })
        except Exception:
            pass

        try:
            for event in fetch_trade_policy_events(limit=10):
                text = event.get("text", "").lower()
                meta = event.get("metadata", {})
                if node_lower in text or node_loc_lower in text:
                    results.append({
                        "news_id": event.get("reference_id", ""),
                        "headline": meta.get("title", ""),
                        "region": "",
                        "date": event.get("event_time", ""),
                        "relevance_score": 0.85,
                    })
        except Exception:
            pass

        return results[:5]

    def _find_risks_for_node(self, node: Node) -> list[dict]:
        """Build risk history entries from live intelligence for this node."""
        from datetime import datetime, timezone

        risks = []
        if node.direct_risk >= 0.6:
            risks.append({
                "risk_id": f"risk_{node.id}",
                "severity": "critical" if node.direct_risk >= 0.8 else "high",
                "disruption_type": "weather_or_trade",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "summary": f"Live intelligence indicates elevated risk at {node.name} ({node.location})",
                "source": "live_intelligence",
            })
        if node.derived_risk >= 0.3:
            risks.append({
                "risk_id": f"derived_{node.id}",
                "severity": "high" if node.derived_risk >= 0.5 else "medium",
                "disruption_type": "cascading_risk",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "summary": f"Upstream disruption propagating to {node.name}",
                "source": "risk_propagation",
            })
        return risks
