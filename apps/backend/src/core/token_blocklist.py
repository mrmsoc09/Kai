"""
JWT Token Blocklist
Stores revoked JWT IDs (jti) in Redis so that logout actually invalidates tokens.
Falls back to a no-op when Redis is not configured (tokens expire naturally).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_redis_unavailable = False  # circuit-breaker to avoid repeated failed connects


def _get_redis():
    global _redis_client, _redis_unavailable
    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    url = os.getenv("REDIS_URL")
    if not url:
        _redis_unavailable = True
        return None
    try:
        import redis
        client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=1)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as exc:
        logger.warning("token_blocklist: Redis unavailable (%s); logout will not revoke tokens", exc)
        _redis_unavailable = True
        return None


_BLOCKLIST_PREFIX = "jti_block:"


def revoke_token(jti: str, exp: int) -> None:
    """
    Mark a JWT as revoked until its natural expiry.

    Args:
        jti: The JWT ID claim from the token.
        exp: The JWT exp claim (Unix timestamp).
    """
    r = _get_redis()
    if r is None:
        return
    ttl = max(1, exp - int(time.time()))
    try:
        r.set(f"{_BLOCKLIST_PREFIX}{jti}", "1", ex=ttl)
    except Exception as exc:
        logger.warning("token_blocklist: failed to revoke jti=%s: %s", jti, exc)


def is_revoked(jti: Optional[str]) -> bool:
    """
    Return True if the given jti has been revoked.

    Args:
        jti: The JWT ID claim (may be None for old tokens without jti).
    """
    if not jti:
        return False
    r = _get_redis()
    if r is None:
        return False
    try:
        return bool(r.exists(f"{_BLOCKLIST_PREFIX}{jti}"))
    except Exception as exc:
        logger.warning("token_blocklist: failed to check jti=%s: %s", jti, exc)
        return False
