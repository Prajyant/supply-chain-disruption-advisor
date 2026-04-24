"""Graph model for digital twin network visualization."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
        return self._weight

    @weight.setter
    def weight(self, value: float) -> None:
        """Set edge weight directly."""
        self._weight = value


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
