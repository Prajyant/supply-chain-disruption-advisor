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
        self.graph = SupplyChainGraph()
        self.propagation_factor: float = 0.3
        self.propagation_threshold: float = 0.6

    def load_sample_graph(self) -> None:
        """Load a sample supply chain graph for demonstration."""
        # Create sample nodes
        suppliers = [
            Node("supplier_001", NodeType.SUPPLIER, "Acme Parts", "Shanghai, China", criticality="high"),
            Node("supplier_002", NodeType.SUPPLIER, "Global Components", "Taipei, Taiwan", criticality="medium"),
            Node("supplier_003", NodeType.SUPPLIER, "Tech Materials", "Seoul, South Korea", criticality="high"),
            Node("supplier_004", NodeType.SUPPLIER, "Precision Parts", "Tokyo, Japan", criticality="low"),
        ]

        warehouses = [
            Node("warehouse_001", NodeType.WAREHOUSE, "West Coast Hub", "Los Angeles, USA", criticality="high"),
            Node("warehouse_002", NodeType.WAREHOUSE, "East Coast Hub", "Newark, USA", criticality="medium"),
        ]

        plants = [
            Node("plant_001", NodeType.PLANT, "Assembly Plant A", "Detroit, USA", criticality="high"),
            Node("plant_002", NodeType.PLANT, "Assembly Plant B", "Chicago, USA", criticality="medium"),
        ]

        # Add nodes to graph
        for node in suppliers + warehouses + plants:
            self.graph.add_node(node)

        # Create edges
        edges = [
            Edge("supplier_001", "warehouse_001", EdgeType.SUPPLIES_TO, "electronics", 5000, 14),
            Edge("supplier_002", "warehouse_001", EdgeType.SUPPLIES_TO, "components", 3000, 10),
            Edge("supplier_003", "warehouse_002", EdgeType.SUPPLIES_TO, "materials", 4000, 12),
            Edge("supplier_004", "warehouse_002", EdgeType.SUPPLIES_TO, "parts", 2000, 8),
            Edge("warehouse_001", "plant_001", EdgeType.SHIPS_TO, "assemblies", 6000, 2),
            Edge("warehouse_002", "plant_002", EdgeType.SHIPS_TO, "assemblies", 5000, 3),
            Edge("warehouse_001", "warehouse_002", EdgeType.SHIPS_TO, "transfer", 1000, 5),
        ]

        for edge in edges:
            self.graph.add_edge(edge)

        self.graph.last_updated = "2026-04-24T10:30:00Z"

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
