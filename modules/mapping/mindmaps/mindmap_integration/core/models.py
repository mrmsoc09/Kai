"""
Data models for mindmap representation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid


class NodeType(Enum):
    ROOT = "root"
    BRANCH = "branch"
    LEAF = "leaf"
    SECURITY_RISK = "security_risk"
    COMPONENT = "component"
    DATA_FLOW = "data_flow"
    IDEA = "idea"
    QUESTION = "question"


class EdgeType(Enum):
    DEPENDS = "depends"
    CALLS = "calls"
    IMPORTS = "imports"
    VULNERABLE = "vulnerable"
    RELATES = "relates"
    SUGGESTS = "suggests"


@dataclass
class Node:
    id: str
    label: str
    type: NodeType = NodeType.BRANCH
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    depth: int = 0
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type.value,
            "metadata": self.metadata,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "depth": self.depth
        }


@dataclass
class Edge:
    source: str
    target: str
    label: Optional[str] = None
    type: EdgeType = EdgeType.RELATES
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "type": self.type.value,
            "metadata": self.metadata
        }


@dataclass
class MindMap:
    title: str
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    format_type: str = "mermaid"
    
    def add_node(self, node: Node) -> str:
        self.nodes[node.id] = node
        return node.id
    
    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)
        if edge.source in self.nodes and edge.target in self.nodes:
            if edge.target not in self.nodes[edge.source].children_ids:
                self.nodes[edge.source].children_ids.append(edge.target)
    
    def get_root(self) -> Optional[Node]:
        for node in self.nodes.values():
            if node.type == NodeType.ROOT:
                return node
        return None
    
    def get_children(self, node_id: str) -> List[Node]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children_ids if cid in self.nodes]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "format_type": self.format_type,
            "metadata": self.metadata,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges]
        }
