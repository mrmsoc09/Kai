from __future__ import annotations

from apps.backend.src.core import hybrid_retriever as hr


def test_hybrid_retriever_merges_vector_and_graph(monkeypatch):
    class _VS:
        def search(self, query, top_k=10, min_score=0.2):
            return [
                {"id": "doc-1", "score": 0.8, "text": "SQL injection finding", "meta": {"source": "vector"}},
                {"id": "node-2", "score": 0.4, "text": "example.com run", "meta": {"source": "vector"}},
            ]

    monkeypatch.setattr(hr, "VectorStore", lambda: _VS())
    monkeypatch.setattr(
        hr,
        "build_graph",
        lambda: {
            "nodes": [
                {"id": "node-2", "type": "run", "label": "example.com run"},
                {"id": "node-3", "type": "query", "label": "sql query trail"},
            ],
            "edges": [],
        },
    )

    out = hr.hybrid_retrieve("sql", top_k=5, min_score=0.1)
    assert out["count"] >= 2
    assert any(r["id"] == "doc-1" for r in out["results"])
    assert any(r["id"] == "node-3" for r in out["results"])


def test_hybrid_retriever_provenance_field(monkeypatch):
    class _VS:
        def search(self, query, top_k=10, min_score=0.2):
            return [{"id": "node-1", "score": 0.7, "text": "x", "meta": {"source": "vector"}}]

    monkeypatch.setattr(hr, "VectorStore", lambda: _VS())
    monkeypatch.setattr(hr, "build_graph", lambda: {"nodes": [{"id": "node-1", "type": "run", "label": "x"}], "edges": []})

    out = hr.hybrid_retrieve("x", top_k=5, min_score=0.1)
    assert out["results"][0]["provenance"] in {"vector+graph", "vector", "graph"}
