from typing import List, Tuple
import os
import numpy as np

_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

_model = None

def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    except Exception:
        _model = None
    return _model

def embed_texts(texts: List[str]) -> np.ndarray:
    mdl = _load_model()
    if mdl is not None:
        vecs = mdl.encode(texts, normalize_embeddings=True)
        return np.array(vecs, dtype=np.float32)
    # Fallback deterministic hashing to _DIM dims
    vecs = []
    for t in texts:
        h = np.zeros((_DIM,), dtype=np.float32)
        if not t:
            vecs.append(h)
            continue
        # simple feature-hash by 4-gram
        for i in range(len(t)-3):
            g = t[i:i+4].encode('utf-8')
            idx = (int.from_bytes(__import__('hashlib').sha256(g).digest()[:4], 'big')) % _DIM
            h[idx] += 1.0
        # L2 normalize
        norm = np.linalg.norm(h)
        if norm > 0:
            h /= norm
        vecs.append(h)
    return np.stack(vecs, axis=0)
