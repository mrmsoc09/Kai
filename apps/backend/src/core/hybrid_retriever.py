from __future__ import annotations

from typing import Any, Dict, List

from .graph import build_graph
from .vector_store import VectorStore


def _graph_search(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        return []
    graph = build_graph()
    matches: List[Dict[str, Any]] = []
    for node in graph.get("nodes", []):
        label = str(node.get("label") or "").lower()
        if not label:
            continue
        if q in label:
            score = min(1.0, 0.55 + (len(q) / max(len(label), 1)) * 0.45)
            matches.append(
                {
                    "id": node.get("id"),
                    "score": float(score),
                    "text": node.get("label"),
                    "meta": {"source": "graph", "node_type": node.get("type")},
                }
            )
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:top_k]


def hybrid_retrieve(query: str, top_k: int = 10, min_score: float = 0.2) -> Dict[str, Any]:
    """
    Hybrid retrieval combining vector and graph results with provenance-aware ranking.
    """
    vector_hits = VectorStore().search(query, top_k=top_k * 2, min_score=min_score)
    graph_hits = _graph_search(query, top_k=top_k * 2)

    merged: Dict[str, Dict[str, Any]] = {}

    for hit in vector_hits:
        hid = str(hit.get("id"))
        merged[hid] = {
            "id": hid,
            "text": hit.get("text"),
            "vector_score": float(hit.get("score") or 0.0),
            "graph_score": 0.0,
            "meta": dict(hit.get("meta") or {}),
        }
        merged[hid]["meta"]["source"] = merged[hid]["meta"].get("source") or "vector"

    for hit in graph_hits:
        hid = str(hit.get("id"))
        if hid not in merged:
            merged[hid] = {
                "id": hid,
                "text": hit.get("text"),
                "vector_score": 0.0,
                "graph_score": float(hit.get("score") or 0.0),
                "meta": dict(hit.get("meta") or {}),
            }
        else:
            merged[hid]["graph_score"] = max(merged[hid]["graph_score"], float(hit.get("score") or 0.0))
            merged[hid]["meta"]["source"] = "vector+graph"

    ranked = []
    for row in merged.values():
        combined = (0.65 * row["vector_score"]) + (0.35 * row["graph_score"])
        if combined < min_score:
            continue
        ranked.append(
            {
                "id": row["id"],
                "text": row["text"],
                "score": round(combined, 4),
                "vector_score": round(row["vector_score"], 4),
                "graph_score": round(row["graph_score"], 4),
                "meta": row["meta"],
                "provenance": row["meta"].get("source"),
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)

    return {
        "query": query,
        "count": len(ranked[:top_k]),
        "results": ranked[:top_k],
        "debug": {
            "vector_hits": len(vector_hits),
            "graph_hits": len(graph_hits),
            "merged_candidates": len(merged),
        },
    }
