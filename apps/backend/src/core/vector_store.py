from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os
import re
import logging

from apps.backend.src.core.qdrant_vector import QdrantVectorStore # type: ignore
from apps.backend.src.core.embeddings_client import EmbeddingClient # type: ignore

logger = logging.getLogger(__name__)

_GLOBAL_MEM: dict[str, dict] = {}

class VectorStore:
    def __init__(self):
        self._mem = _GLOBAL_MEM  # shared in-process store
        self._pg = None
        self._qdrant = None
        self._embedding_client = None

        qdrant_url = os.environ.get('QDRANT_URL')
        if qdrant_url:
            qdrant_api_key = os.environ.get('QDRANT_API_KEY')
            qdrant_collection = os.environ.get('QDRANT_COLLECTION_NAME', 'k1_collection')
            try:
                self._qdrant = QdrantVectorStore(url=qdrant_url, api_key=qdrant_api_key, collection_name=qdrant_collection)
                if not getattr(self._qdrant, 'available', False):
                    self._qdrant = None # If not available, don't use it
            except Exception as e:
                logger.error(f"Failed to initialize Qdrant client: {e}")
                self._qdrant = None

        if self._qdrant is None: # Only try PG if Qdrant is not configured or failed to initialize
            dsn = os.environ.get('PGVECTOR_DSN')
            if dsn:
                try:
                    try:
                        from apps.backend.src.core.vector_pg import PGVectorStore  # type: ignore
                    except Exception:  # pragma: no cover - compatibility fallback
                        from core.vector_pg import PGVectorStore  # type: ignore
                    pg = PGVectorStore(dsn)
                    if getattr(pg, 'available', False):
                        self._pg = pg
                except Exception as e:
                    logger.error(f"Failed to initialize PGVectorStore: {e}")
                    self._pg = None

        if self._qdrant is not None or self._pg is not None: # Initialize EmbeddingClient if any external vector store is active
            self._embedding_client = EmbeddingClient()

    @staticmethod
    def _tokens(text: str) -> List[str]:
        if not text:
            return []
        t = (text or '').lower()
        toks = re.findall(r"[a-z0-9_./:-]+", t)
        # basic singularization (very simple)
        base: List[str] = []
        for tok in toks:
            if tok.endswith('s') and len(tok) > 3:
                base.append(tok[:-1])
            base.append(tok)
        # vulnerability acronym + synonym expansion
        syn_map = {
            'sqli': ['sql', 'injection', 'sqlinjection', 'boolean', 'blind'],
            'sql-injection': ['sql', 'injection'],
            'sqlinjection': ['sql', 'injection'],
            'xss': ['cross', 'site', 'scripting', 'xss'],
            'csrf': ['cross', 'site', 'request', 'forgery', 'csrf'],
            'ssrf': ['server', 'side', 'request', 'forgery', 'ssrf'],
            'rce': ['remote', 'code', 'execution', 'rce'],
            'lfi': ['local', 'file', 'inclusion', 'lfi'],
            'rfi': ['remote', 'file', 'inclusion', 'rfi'],
            'idor': ['insecure', 'direct', 'object', 'reference', 'idor'],
            'xxe': ['xml', 'external', 'entity', 'xxe'],
            'openredirect': ['open', 'redirect'],
            'open-redirect': ['open', 'redirect'],
        }
        expanded: List[str] = []
        for tok in base:
            expanded.append(tok)
            if tok in syn_map:
                expanded.extend(syn_map[tok])
        return [x for x in expanded if x]

    @staticmethod
    def _jaccard(a: List[str], b: List[str]) -> float:
        sa, sb = set(a), set(b)
        if not sa and not sb:
            return 0.0
        inter = len(sa & sb)
        union = len(sa | sb) or 1
        return inter / union

    def upsert(self, items: List[Dict[str, Any]]) -> int:
        # Prefer Qdrant first (best effort)
        if self._qdrant is not None:
            try:
                self._qdrant.upsert(items)
            except Exception:
                pass
        # Then try PG (best effort)
        if self._pg is not None:
            try:
                self._pg.upsert(items)
            except Exception:
                pass
        # Always maintain memory copy as a fallback/cache
        for item in items:
            _id = str(item.get('id'))
            text = item.get('text') or ''
            meta = item.get('meta') or {}
            # Store vector for Qdrant/PGVector later if it exists
            vector = item.get('vector')
            self._mem[_id] = {
                'text': text,
                'meta': meta,
                'tokens': self._tokens(text),
                'vector': vector # Store vector in memory for consistent behavior
            }
        return len(items)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.2) -> List[Dict[str, Any]]:
        query_vector: Optional[List[float]] = None
        if self._embedding_client is not None:
            try:
                query_vector = self._embedding_client.embed(query)
            except Exception as e:
                logger.warning(f"Failed to embed query for vector search: {e}")

        # Prefer Qdrant if available and we have a query vector
        if self._qdrant is not None and query_vector is not None:
            try:
                res = self._qdrant.search(query_vector=query_vector, top_k=top_k, min_score=min_score)
                if res:
                    return res
            except Exception as e:
                logger.error(f"Qdrant search failed: {e}")

        # Then try PG if available and we have a query vector
        if self._pg is not None and query_vector is not None:
            try:
                res = self._pg.search(query_vector=query_vector, top_k=top_k, min_score=min_score)
                if res:
                    return res
            except Exception as e:
                logger.error(f"PostgreSQL vector search failed: {e}")

        # Fallback to in-memory Jaccard similarity search
        qtok = self._tokens(query or '')
        scored: List[Tuple[str, float]] = []
        for _id, rec in self._mem.items():
            dtok = rec.get('tokens') or []
            j = self._jaccard(qtok, dtok)
            if qtok and dtok:
                inter = len(set(qtok) & set(dtok))
                cov_q = inter / max(1, len(set(qtok)))
                cov_d = inter / max(1, len(set(dtok)))
            else:
                cov_q = cov_d = 0.0
            score = max(j, cov_q, cov_d * 0.9)
            if score >= min_score:
                scored.append((_id, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        out: List[Dict[str, Any]] = []
        for _id, score in scored[: top_k]:
            rec = self._mem[_id]
            out.append({'id': _id, 'score': float(score), 'text': rec.get('text'), 'meta': rec.get('meta')})
        return out

    def info(self) -> Dict[str, Any]:
        if self._qdrant is not None:
            return self._qdrant.info()
        if self._pg is not None:
            return self._pg.info()
        return {
            'backend': 'memory',
            'mem_count': len(self._mem),
        }
