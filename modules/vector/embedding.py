from __future__ import annotations
import re, math, json, os, hashlib
from typing import List, Dict, Any, Iterable, Tuple

DIM = 512
TOKEN_RE = re.compile(r"[A-Za-z0-9_\-\.]+")

def tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")] 

def embed_text(text: str, dim: int = DIM) -> List[float]:
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = int(hashlib.md5(tok.encode('utf-8')).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0
    # L2 normalize
    norm = math.sqrt(sum(v*v for v in vec)) or 1.0
    return [v / norm for v in vec]

def cosine(a: List[float], b: List[float]) -> float:
    return sum(x*y for x,y in zip(a,b))

def build_index(rows: Iterable[Dict[str, Any]], text_fields: List[str], out_jsonl: str) -> str:
    os.makedirs(os.path.dirname(out_jsonl), exist_ok=True)
    with open(out_jsonl, 'w', encoding='utf-8') as f:
        for r in rows:
            txt = ' '.join(str(r.get(k) or '') for k in text_fields)
            emb = embed_text(txt)
            rec = {**r, '_vector': emb}
            f.write(json.dumps(rec) + '\n')
    return out_jsonl

def load_index(jsonl_path: str) -> List[Dict[str, Any]]:
    out = []
    if not os.path.exists(jsonl_path):
        return out
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out

def search(index: List[Dict[str, Any]], query: str, k: int = 20) -> List[Tuple[float, Dict[str, Any]]]:
    qv = embed_text(query)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for r in index:
        v = r.get('_vector')
        if not isinstance(v, list):
            continue
        score = cosine(qv, [float(x) for x in v])
        scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:k]
