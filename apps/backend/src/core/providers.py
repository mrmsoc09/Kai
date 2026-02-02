from __future__ import annotations
from typing import Dict, Any
import os

BAD_MODELS = { 'gpt-2.5' }

def _valid(name: str|None) -> bool:
    if not name or not str(name).strip():
        return False
    n = str(name).strip().lower()
    if n in BAD_MODELS:
        return False
    # Minimal sanity: known vendor prefixes accepted
    allow_prefix = (
        n.startswith('gemini/') or
        n.startswith('claude-') or
        n.startswith('gpt-') or
        n.startswith('text-embedding-') or
        n.startswith('nomic-') or
        n.startswith('e5-') or
        n.startswith('bge-') or
        n.startswith('cohere-')
    )
    return allow_prefix

def get_provider_config() -> Dict[str, Any]:
    cfg = {
        'preferred': os.environ.get('K1_PROVIDER_PREFERRED', 'gemini'),
        'models': {
            'gemini': os.environ.get('K1_MODEL_GEMINI'),
            'anthropic': os.environ.get('K1_MODEL_ANTHROPIC'),
            'openai': os.environ.get('K1_MODEL_OPENAI'),
            'embeddings': os.environ.get('K1_MODEL_EMBEDDINGS', 'text-embedding-3-large'),
            'rerank': os.environ.get('K1_MODEL_RERANK'),
        }
    }
    # Attach validity flags
    val: Dict[str, Any] = {}
    for k, v in cfg['models'].items():
        val[k] = {
            'name': v,
            'valid': _valid(v)
        }
    cfg['models'] = val
    return cfg
