from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Iterable
import json, math, hashlib, re

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / 'artifacts'
EMB = ART / 'embeddings.jsonl'
EMB.parent.mkdir(parents=True, exist_ok=True)

DIM = 256
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text: str) -> List[str]:
    return TOKEN_RE.findall((text or '').lower())


def _hash_to_idx(tok: str) -> int:
    h = hashlib.blake2b(tok.encode('utf-8'), digest_size=4).digest()
    return int.from_bytes(h, 'little') % DIM


def embed_text(text: str) -> List[float]:
    vec = [0.0] * DIM
    toks = _tokens(text)
    if not toks:
        return vec
    for t in toks:
        vec[_hash_to_idx(t)] += 1.0
    # L2 normalize
    norm = math.sqrt(sum(v*v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: List[float], b: List[float]) -> float:
    return sum(x*y for x, y in zip(a, b))


def upsert_embeddings(run_id: str, items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    count = 0
    with EMB.open('a', encoding='utf-8') as f:
        for it in items:
            text = (it.get('text') or '').strip()
            if not text:
                continue
            entry = {
                'run_id': run_id,
                'type': it.get('type') or 'generic',
                'text': text,
                'vec': embed_text(text),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1
    return {'ok': True, 'count': count}


def _load_all() -> List[Dict[str, Any]]:
    if not EMB.exists():
        return []
    out: List[Dict[str, Any]] = []
    with EMB.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def search_similar(text: str, top_k: int = 5, min_score: float = 0.7) -> Dict[str, Any]:
    qv = embed_text(text)
    entries = _load_all()
    scored = []
    for e in entries:
        vec = e.get('vec') or []
        if not vec or len(vec) != DIM:
            continue
        score = cosine(qv, vec)
        if score >= min_score:
            scored.append({'run_id': e.get('run_id'), 'type': e.get('type'), 'text': e.get('text'), 'score': round(float(score), 4)})
    scored.sort(key=lambda x: x['score'], reverse=True)
    return {'ok': True, 'matches': scored[:top_k]}
