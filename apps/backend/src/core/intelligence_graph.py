"""
Intelligence Relationship Graph
==================================
Manages relationships between memory entries. Memory is NOT flat.

Supported edge types:
  finding      → endpoint         (a finding occurred at an endpoint)
  finding      → exploit_pattern  (a finding has a known exploit pattern)
  exploit_pat  → tool_sequence    (exploit pattern is triggered by tool sequence)
  endpoint     → tech_stack       (endpoint fingerprint → tech it runs on)
  vuln         → vuln             (vulnerability chaining — A enables B)
  mission      → finding          (which findings a mission produced)
  pattern_sig  → finding          (signature covers multiple findings)

Graph structure:
  Adjacency list stored as JSON file: artifacts/intelligence/graph.json
  In-memory cache + dirty-write for performance.

Thread-safe via lock.

Usage::

    graph = IntelligenceGraph()
    graph.add_edge("mem-001", "mem-002", EdgeType.FINDING_TO_EXPLOIT)
    neighbors = graph.get_neighbors("mem-001")
    chain = graph.find_exploit_chain("mem-001", max_depth=4)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------------


class EdgeType(str, Enum):
    FINDING_TO_ENDPOINT = "finding_to_endpoint"
    FINDING_TO_EXPLOIT = "finding_to_exploit"
    EXPLOIT_TO_TOOL_SEQ = "exploit_to_tool_seq"
    ENDPOINT_TO_TECH = "endpoint_to_tech"
    VULN_CHAINS_TO = "vuln_chains_to"       # vuln A enables vuln B
    MISSION_TO_FINDING = "mission_to_finding"
    PATTERN_COVERS = "pattern_covers"        # signature → individual findings
    SIMILAR_TO = "similar_to"               # soft similarity link


# ---------------------------------------------------------------------------
# Edge record
# ---------------------------------------------------------------------------


@dataclass
class Edge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    created_at: float = field(default_factory=time.time)
    weight: float = 1.0         # relevance weight (higher = stronger link)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "created_at": self.created_at,
            "weight": self.weight,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(
            source_id=d["source_id"],
            target_id=d["target_id"],
            edge_type=EdgeType(d["edge_type"]),
            created_at=d.get("created_at", time.time()),
            weight=d.get("weight", 1.0),
            metadata=d.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def _graph_path() -> Path:
    env = os.getenv("K1_ARTIFACTS_ROOT", "").strip()
    root = Path(env) if env else Path("artifacts")
    return root / "intelligence" / "graph.json"


class IntelligenceGraph:
    """
    Adjacency-list graph for intelligence memory relationships.

    Stored as:
      {
        "edges": [<edge dict>, ...],
        "adjacency": {"node_id": [<edge dict>, ...]}  — outbound edges index
      }

    Reverse edges (inbound) are maintained in _reverse_adj for O(1) lookup.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _graph_path()
        self._lock = threading.Lock()
        # adjacency: node_id → list of outbound Edge
        self._adj: dict[str, list[Edge]] = {}
        # reverse: node_id → list of inbound Edge
        self._reverse: dict[str, list[Edge]] = {}
        self._dirty = False
        self._load()

    # -- Persistence -----------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for ed in data.get("edges", []):
                edge = Edge.from_dict(ed)
                self._add_to_adj(edge)
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("intelligence_graph.load_failed err=%s", e)

    def _flush(self) -> None:
        """Persist to disk. Called under lock."""
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        all_edges = [
            edge.to_dict()
            for edges in self._adj.values()
            for edge in edges
        ]
        data = {"edges": all_edges}
        tmp = self._path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data), encoding="utf-8")
            tmp.replace(self._path)
            self._dirty = False
        except OSError as e:
            logger.error("intelligence_graph.flush_failed err=%s", e)

    def _add_to_adj(self, edge: Edge) -> None:
        """Add edge to adjacency structures (no lock — caller holds lock)."""
        self._adj.setdefault(edge.source_id, []).append(edge)
        self._reverse.setdefault(edge.target_id, []).append(edge)

    # -- Mutation API ----------------------------------------------------------

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> Edge:
        """Add a directed edge between two memory entries."""
        edge = Edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata or {},
        )
        with self._lock:
            # Avoid duplicate edges (same src, tgt, type)
            existing = self._adj.get(source_id, [])
            for e in existing:
                if e.target_id == target_id and e.edge_type == edge_type:
                    return e  # already exists
            self._add_to_adj(edge)
            self._dirty = True
            self._flush()
        return edge

    def remove_edges(self, node_id: str) -> int:
        """Remove all edges involving node_id. Returns count removed."""
        with self._lock:
            outbound = self._adj.pop(node_id, [])
            inbound = self._reverse.pop(node_id, [])
            removed = len(outbound) + len(inbound)
            # Clean reverse/adj structures
            for edge in outbound:
                self._reverse.get(edge.target_id, [])[:] = [
                    e for e in self._reverse.get(edge.target_id, [])
                    if e.source_id != node_id
                ]
            for edge in inbound:
                self._adj.get(edge.source_id, [])[:] = [
                    e for e in self._adj.get(edge.source_id, [])
                    if e.target_id != node_id
                ]
            if removed:
                self._dirty = True
                self._flush()
        return removed

    # -- Query API -------------------------------------------------------------

    def get_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
        direction: str = "outbound",  # "outbound", "inbound", "both"
    ) -> list[Edge]:
        """Return edges connected to node_id, optionally filtered by type."""
        with self._lock:
            if direction == "outbound":
                edges = list(self._adj.get(node_id, []))
            elif direction == "inbound":
                edges = list(self._reverse.get(node_id, []))
            else:
                edges = list(self._adj.get(node_id, [])) + list(self._reverse.get(node_id, []))

        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return sorted(edges, key=lambda e: e.weight, reverse=True)

    def find_exploit_chain(
        self, start_id: str, max_depth: int = 4
    ) -> list[list[str]]:
        """
        BFS from start_id following VULN_CHAINS_TO and FINDING_TO_EXPLOIT edges.

        Returns a list of paths (each path is a list of memory_ids).
        Enables "what does this vulnerability lead to?" queries.
        """
        chain_edge_types = {EdgeType.VULN_CHAINS_TO, EdgeType.FINDING_TO_EXPLOIT}
        paths: list[list[str]] = []
        queue: list[tuple[str, list[str]]] = [(start_id, [start_id])]
        visited: set[str] = {start_id}

        while queue:
            node, path = queue.pop(0)
            if len(path) > max_depth:
                continue
            for edge in self.get_neighbors(node, direction="outbound"):
                if edge.edge_type not in chain_edge_types:
                    continue
                target = edge.target_id
                if target in visited:
                    continue
                new_path = path + [target]
                paths.append(new_path)
                visited.add(target)
                queue.append((target, new_path))

        return paths

    def find_similar(self, node_id: str) -> list[str]:
        """Return memory_ids linked via SIMILAR_TO edges (both directions)."""
        edges = self.get_neighbors(node_id, EdgeType.SIMILAR_TO, direction="both")
        similar = set()
        for e in edges:
            similar.add(e.source_id if e.target_id == node_id else e.target_id)
        similar.discard(node_id)
        return list(similar)

    def get_all_findings_for_mission(self, mission_id: str) -> list[str]:
        """Return memory_ids of all findings linked to a mission."""
        edges = self.get_neighbors(mission_id, EdgeType.MISSION_TO_FINDING, direction="outbound")
        return [e.target_id for e in edges]

    def node_count(self) -> int:
        with self._lock:
            return len(self._adj)

    def edge_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._adj.values())

    def to_summary(self) -> dict[str, Any]:
        with self._lock:
            type_counts: dict[str, int] = {}
            for edges in self._adj.values():
                for edge in edges:
                    type_counts[edge.edge_type.value] = type_counts.get(edge.edge_type.value, 0) + 1
        return {
            "node_count": self.node_count(),
            "edge_count": self.edge_count(),
            "edge_type_breakdown": type_counts,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_graph_instance: IntelligenceGraph | None = None
_graph_lock = threading.Lock()


def get_intelligence_graph() -> IntelligenceGraph:
    global _graph_instance
    with _graph_lock:
        if _graph_instance is None:
            _graph_instance = IntelligenceGraph()
        return _graph_instance
