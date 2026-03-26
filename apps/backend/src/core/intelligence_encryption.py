"""
Intelligence Encryption Layer
================================
Encrypts all memory payloads at rest. Decrypts only on access.

Architecture:
  - Primary: AES-128 via Fernet (symmetric, authenticated encryption)
  - Key sources (in priority order):
      1. K1_INTELLIGENCE_MASTER_KEY env var (hex or base64 Fernet key)
      2. K1_TENANT_{TENANT_ID}_KEY env var (per-tenant override)
      3. Derived from JWT_SECRET_KEY (fallback — dev only)
  - If cryptography package unavailable: base64 obfuscation with loud warning
    (NOT secure — for development only)

All payloads are stored as:
  {"enc": "<fernet_token_b64>", "alg": "fernet", "kid": "<key_id>"}

  Or when cryptography is unavailable:
  {"enc": "<b64>", "alg": "plain-b64", "kid": "none"}

Security properties:
  - Authenticated encryption — tampering is detected
  - Key rotation: change K1_INTELLIGENCE_MASTER_KEY and re-encrypt (offline tool)
  - Per-tenant isolation: different key per tenant namespace
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import warnings
from typing import Any

from .secret_manager import get_secret_manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cryptography availability
# ---------------------------------------------------------------------------

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore

    _HAVE_CRYPTO = True
except ImportError:  # pragma: no cover
    _HAVE_CRYPTO = False
    warnings.warn(
        "cryptography package not installed. Intelligence memory will use base64 "
        "obfuscation — NOT secure for production. Install: pip install cryptography",
        RuntimeWarning,
        stacklevel=1,
    )

# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------

_KEY_CACHE: dict[str, bytes] = {}  # kid → raw 32-byte key material


def _resolve_key(tenant_id: str | None = None) -> tuple[bytes, str]:
    """
    Resolve the encryption key for a given tenant.

    Returns (key_bytes, key_id).
    Key bytes are 32 raw bytes (used to derive Fernet key via HKDF-lite).
    """
    cache_key = tenant_id or "__platform__"
    if cache_key in _KEY_CACHE:
        return _KEY_CACHE[cache_key], cache_key

    # 1. Per-tenant key
    if tenant_id:
        env_name = f"K1_TENANT_{tenant_id.upper().replace('-', '_')}_KEY"
        raw = os.getenv(env_name, "").strip()
        if raw:
            material = _decode_key_material(raw)
            _KEY_CACHE[cache_key] = material
            return material, cache_key

    # 2. Platform master key
    master_raw = os.getenv("K1_INTELLIGENCE_MASTER_KEY", "").strip()
    if master_raw:
        material = _decode_key_material(master_raw)
        _KEY_CACHE[cache_key] = material
        return material, "__platform__"

    # 3. Derive from JWT secret (dev fallback)
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    if not jwt_secret:
        jwt_secret = get_secret_manager().get_optional("K1_JWT_SECRET") or ""
    if jwt_secret:
        logger.warning(
            "intelligence_encryption: using JWT_SECRET_KEY as fallback key — "
            "set K1_INTELLIGENCE_MASTER_KEY for production"
        )
        material = hashlib.sha256(f"k1-intel-{jwt_secret}".encode()).digest()
        _KEY_CACHE[cache_key] = material
        return material, "__jwt-derived__"

    # 4. Last resort: ephemeral random key (data not recoverable across restarts)
    logger.error(
        "intelligence_encryption: no key configured — using ephemeral random key. "
        "Encrypted memories WILL NOT survive restart. Set K1_INTELLIGENCE_MASTER_KEY."
    )
    material = os.urandom(32)
    _KEY_CACHE[cache_key] = material
    return material, "__ephemeral__"


def _decode_key_material(raw: str) -> bytes:
    """Decode hex or base64-encoded key material into 32 bytes."""
    # Try hex (64 chars = 32 bytes)
    try:
        decoded = bytes.fromhex(raw)
        return hashlib.sha256(decoded).digest()  # normalize to 32 bytes
    except ValueError:
        pass
    # Try base64
    try:
        decoded = base64.b64decode(raw + "==")  # pad for safety
        return hashlib.sha256(decoded).digest()
    except Exception:
        pass
    # Treat as passphrase
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _material_to_fernet_key(material: bytes) -> "Fernet":
    """Convert 32-byte material to a Fernet instance (Fernet requires URL-safe base64 of 32 bytes)."""
    fernet_key = base64.urlsafe_b64encode(material)
    return Fernet(fernet_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def encrypt_payload(data: Any, tenant_id: str | None = None) -> dict[str, str]:
    """
    Encrypt a Python object (dict, list, str, etc.) for storage.

    Returns a dict suitable for JSON serialization:
      {"enc": "<token>", "alg": "fernet"|"plain-b64", "kid": "<key_id>"}
    """
    raw_bytes = json.dumps(data, default=str).encode("utf-8")
    material, kid = _resolve_key(tenant_id)

    if _HAVE_CRYPTO:
        f = _material_to_fernet_key(material)
        token = f.encrypt(raw_bytes)
        return {"enc": token.decode("ascii"), "alg": "fernet", "kid": kid}
    else:
        # Development fallback — NOT secure
        obfuscated = base64.b64encode(raw_bytes).decode("ascii")
        return {"enc": obfuscated, "alg": "plain-b64", "kid": "none"}


def decrypt_payload(envelope: dict[str, str], tenant_id: str | None = None) -> Any:
    """
    Decrypt an encrypted envelope produced by encrypt_payload().

    Returns the original Python object.
    Raises ValueError on tamper detection or wrong key.
    """
    alg = envelope.get("alg", "fernet")
    enc = envelope.get("enc", "")

    if alg == "plain-b64":
        raw = base64.b64decode(enc.encode("ascii"))
        return json.loads(raw.decode("utf-8"))

    if alg == "fernet":
        material, _ = _resolve_key(tenant_id)
        if not _HAVE_CRYPTO:
            raise ValueError("cryptography package required to decrypt fernet payloads")
        f = _material_to_fernet_key(material)
        try:
            raw = f.decrypt(enc.encode("ascii"))
        except Exception as e:
            raise ValueError(f"decryption_failed: {e}") from e
        return json.loads(raw.decode("utf-8"))

    raise ValueError(f"unknown_algorithm: {alg}")


def is_encrypted(envelope: Any) -> bool:
    """Check whether an object is an encrypted envelope."""
    return (
        isinstance(envelope, dict)
        and "enc" in envelope
        and "alg" in envelope
    )


def rotate_key_cache() -> None:
    """Clear the in-memory key cache, forcing re-resolution on next access."""
    _KEY_CACHE.clear()


def derive_content_hash(data: Any) -> str:
    """Deterministic content hash for deduplication (computed BEFORE encryption)."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
