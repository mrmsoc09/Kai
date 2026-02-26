from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
import os

try:
    import psycopg
except Exception:  # psycopg may not be installed in local env
    psycopg = None  # type: ignore

DDL = [
    "CREATE EXTENSION IF NOT EXISTS vector;",
    "CREATE TABLE IF NOT EXISTS embeddings (\n"
    "    id TEXT PRIMARY KEY,\n"
    "    text TEXT,\n"
    "    meta JSONB,\n"
    "    vec vector(384)\n"
    ");",
    "CREATE INDEX IF NOT EXISTS idx_embeddings_vec ON embeddings USING ivfflat (vec);",
]

class PGVectorStore:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.environ.get('PGVECTOR_DSN')
        self.available = bool(self.dsn and psycopg is not None)
        self.dim = 384
        if self.available:
            try:
                with psycopg.connect(self.dsn) as conn:
                    with conn.cursor() as cur:
                        for stmt in DDL:
                            cur.execute(stmt)
                    conn.commit()
            except Exception:
                self.available = False

    @staticmethod
    def _hash_embed(text: str, dim: int = 384) -> List[float]:
        # Deterministic simple hashing-based embedding when no model bound
        import hashlib
        import math
        vec = [0.0] * dim
        tokens = (text or '').lower().split()
        for t in tokens:
            h = int(hashlib.sha256(t.encode()).hexdigest(), 16)
            idx = h % dim
            vec[idx] += 1.0
        # L2 normalize
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def upsert(self, items: List[Dict[str, Any]]) -> int:
        if not self.available:
            return 0
        try:
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    for it in items:
                        _id = it.get('id')
                        text = it.get('text') or ''
                        meta = it.get('meta') or {}
                        vec = self._hash_embed(text, self.dim)
                        cur.execute(
                            "INSERT INTO embeddings (id, text, meta, vec) VALUES (%s, %s, %s, %s) "
                            "ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text, meta=EXCLUDED.meta, vec=EXCLUDED.vec",
                            (_id, text, psycopg.types.json.Json(meta), vec),
                        )
                conn.commit()
            return len(items)
        except Exception:
            return 0

    def search(self, query: str, top_k: int = 5, min_score: float = 0.2) -> List[Dict[str, Any]]:
        if not self.available:
            return []
        try:
            qv = self._hash_embed(query or '', self.dim)
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, text, meta, 1 - (vec <=> %s::vector) AS score "
                        "FROM embeddings ORDER BY vec <=> %s::vector ASC LIMIT %s",
                        (qv, qv, top_k),
                    )
                    rows = cur.fetchall()
            out: List[Dict[str, Any]] = []
            for _id, text, meta, score in rows:
                if float(score) >= float(min_score):
                    out.append({'id': _id, 'score': float(score), 'text': text, 'meta': meta})
            return out
        except Exception:
            return []

    def info(self) -> Dict[str, Any]:
        return { 'backend': 'pgvector', 'available': self.available, 'dim': self.dim }
