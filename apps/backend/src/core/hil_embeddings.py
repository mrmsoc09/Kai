from __future__ import annotations

import os
from hashlib import sha256
from typing import List

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
    model = _load_model()
    if model is not None:
        vectors = model.encode(texts, normalize_embeddings=True)
        return np.array(vectors, dtype=np.float32)

    vectors = []
    for text in texts:
        vec = np.zeros((_DIM,), dtype=np.float32)
        if not text:
            vectors.append(vec)
            continue

        for i in range(len(text) - 3):
            gram = text[i : i + 4].encode("utf-8")
            idx = int.from_bytes(sha256(gram).digest()[:4], "big") % _DIM
            vec[idx] += 1.0

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        vectors.append(vec)

    return np.stack(vectors, axis=0)
