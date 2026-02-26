from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os
import re

_GLOBAL_MEM: dict[str, dict] = {}

class VectorStore:
    def __init__(self):
        self._mem = _GLOBAL_MEM  # shared in-process store
        self._pg = None
        dsn = os.environ.get('PGVECTOR_DSN')
        if dsn:
            try:
                from core.vector_pg import PGVectorStore  # type: ignore
                pg = PGVectorStore(dsn)
                if getattr(pg, 'available', False):
                    self._pg = pg
            except Exception:
                self._pg = None

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
        # Try PG first (best effort)
        if self._pg is not None:
            try:
                self._pg.upsert(items)
            except Exception:
                pass
        # Always maintain memory copy
        for item in items:
            _id = str(item.get('id'))
            text = item.get('text') or ''
            meta = item.get('meta') or {}
            self._mem[_id] = {
                'text': text,
                'meta': meta,
                'tokens': self._tokens(text),
            }
        return len(items)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.2) -> List[Dict[str, Any]]:
        # Prefer PG if available
        if self._pg is not None:
            try:
                res = self._pg.search(query, top_k=top_k, min_score=min_score)
                if res:
                    return res
            except Exception:
                pass
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
        return {
            'backend': ('pgvector' if self._pg is not None else 'memory'),
            'mem_count': len(self._mem),
        }
