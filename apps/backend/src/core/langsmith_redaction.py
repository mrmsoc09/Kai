"""
LangSmith Redaction Policy for K1 / Kai Platform
===================================================
Ensures no secrets, credentials, PII, or sensitive payloads leak into
LangSmith traces, evaluation datasets, or experiment logs.

Redaction modes:
  - "strict"   : Redacts API keys, tokens, credentials, target IPs/domains,
                  large payloads (>10KB), raw tool outputs, and PII patterns.
  - "moderate" : Redacts API keys, tokens, credentials. Allows target info
                  and truncated tool outputs.
  - "none"     : No redaction (development/local only — NEVER in production).

Architecture:
  This module is stateless and side-effect-free. It operates on plain dicts
  and returns new dicts without mutating inputs. Called by LangSmithBridge
  before any data is sent to LangSmith.

Security invariants:
  - Vault tokens NEVER appear in traces
  - API keys NEVER appear in traces
  - PGP private keys NEVER appear in traces
  - Raw exploit payloads are truncated + hashed in strict mode
  - Target IP addresses are masked in strict mode
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# -- Redaction patterns --------------------------------------------------------

# Keys that always get redacted (case-insensitive match)
_SECRET_KEY_PATTERNS: frozenset[str] = frozenset({
    "api_key", "apikey", "api_secret", "secret", "password", "passwd",
    "token", "auth_token", "access_token", "refresh_token", "bearer",
    "credential", "credentials", "private_key", "secret_key",
    "vault_token", "pgp_key", "ssh_key", "aws_secret", "aws_access_key",
    "client_secret", "encryption_key", "signing_key", "hmac_key",
    "database_url", "connection_string", "dsn", "redis_url",
    "smtp_password", "mail_password",
})

# Governance-sensitive fields that should not be exported in clear text.
_GOVERNANCE_KEY_PATTERNS: frozenset[str] = frozenset({
    "governance_decision",
    "approval_id",
    "approval_requirements",
    "scope_decision",
    "scope_decision_id",
    "policy_manifest",
    "contract_id",
    "delegation_scope",
})

# Regex patterns for value-level redaction
_VALUE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # API keys (various formats)
    ("api_key", re.compile(r"(?:sk|pk|api|key|token)[_-][a-zA-Z0-9]{20,}", re.IGNORECASE)),
    # Bearer tokens
    ("bearer_token", re.compile(r"Bearer\s+[a-zA-Z0-9._\-]+", re.IGNORECASE)),
    # AWS keys
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    # JWT tokens (3 base64 segments separated by dots)
    ("jwt", re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+")),
    # PGP blocks
    ("pgp_block", re.compile(r"-----BEGIN PGP.*?-----.*?-----END PGP.*?-----", re.DOTALL)),
    # Private keys
    ("private_key", re.compile(r"-----BEGIN.*?PRIVATE KEY-----.*?-----END.*?PRIVATE KEY-----", re.DOTALL)),
]

# IP address pattern (for strict mode)
_IP_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)

# Email pattern (for strict mode PII removal)
_EMAIL_PATTERN = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
)

# Maximum payload size before truncation (bytes)
_STRICT_MAX_VALUE_SIZE = 10_000  # 10 KB
_MODERATE_MAX_VALUE_SIZE = 50_000  # 50 KB

# Keys whose values are tool output / raw data (truncate in strict mode)
_LARGE_PAYLOAD_KEYS: frozenset[str] = frozenset({
    "output", "stdout", "stderr", "raw_output", "tool_output",
    "response_body", "html", "xml", "nmap_xml",
    "exploit_output", "scan_result", "raw_result",
})


# -- Public API ----------------------------------------------------------------


def redact_for_langsmith(
    data: dict[str, Any],
    *,
    mode: str = "strict",
) -> dict[str, Any]:
    """
    Apply redaction policy to a data dict before sending to LangSmith.

    Args:
        data: Input dict (not mutated).
        mode: "strict" | "moderate" | "none".

    Returns:
        New dict with sensitive values redacted.
    """
    if mode == "none":
        return data
    return _redact_dict(data, mode=mode, depth=0)


def redact_string(value: str, *, mode: str = "strict") -> str:
    """
    Apply value-level redaction patterns to a string.

    Args:
        value: Input string.
        mode: "strict" | "moderate" | "none".

    Returns:
        Redacted string.
    """
    if mode == "none":
        return value
    return _redact_string_value(value, mode=mode)


# -- Internal implementation ---------------------------------------------------


def _redact_dict(
    data: dict[str, Any],
    *,
    mode: str,
    depth: int,
) -> dict[str, Any]:
    """Recursively redact a dict. Max depth 15 to prevent stack overflow."""
    if depth > 15:
        return {"_redacted": "max_depth_exceeded"}

    result: dict[str, Any] = {}
    for key, value in data.items():
        result[key] = _redact_value(key, value, mode=mode, depth=depth)
    return result


def _redact_value(
    key: str,
    value: Any,
    *,
    mode: str,
    depth: int,
) -> Any:
    """Redact a single key-value pair based on the key name and value type."""
    key_lower = key.lower().strip()

    # 1. Key-based redaction (always, regardless of mode)
    if _is_secret_key(key_lower):
        return "[REDACTED]"
    if _is_governance_key(key_lower):
        return "[REDACTED:GOVERNANCE]"

    # 2. Handle nested dicts
    if isinstance(value, dict):
        return _redact_dict(value, mode=mode, depth=depth + 1)

    # 3. Handle lists
    if isinstance(value, list):
        return [
            _redact_value(key, item, mode=mode, depth=depth + 1)
            if isinstance(item, (dict, str, list))
            else item
            for item in value
        ]

    # 4. Handle strings
    if isinstance(value, str):
        return _redact_string_entry(key_lower, value, mode=mode)

    return value


def _is_secret_key(key_lower: str) -> bool:
    """Check if a key name matches known secret patterns."""
    return any(pattern in key_lower for pattern in _SECRET_KEY_PATTERNS)


def _is_governance_key(key_lower: str) -> bool:
    """Check if a key name is governance-sensitive."""
    return any(pattern in key_lower for pattern in _GOVERNANCE_KEY_PATTERNS)


def _redact_string_entry(key_lower: str, value: str, *, mode: str) -> str:
    """Redact a string value based on key context and content patterns."""
    # Truncate large payloads
    if key_lower in _LARGE_PAYLOAD_KEYS:
        max_size = (
            _STRICT_MAX_VALUE_SIZE if mode == "strict" else _MODERATE_MAX_VALUE_SIZE
        )
        if len(value) > max_size:
            content_hash = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]
            return (
                f"{value[:max_size]}... "
                f"[TRUNCATED: {len(value)} bytes, sha256:{content_hash}]"
            )

    # Value-level pattern redaction
    return _redact_string_value(value, mode=mode)


def _redact_string_value(value: str, *, mode: str) -> str:
    """Apply regex-based value redaction patterns."""
    result = value

    # Always redact secret patterns in values
    for pattern_name, pattern in _VALUE_PATTERNS:
        result = pattern.sub(f"[REDACTED:{pattern_name}]", result)

    # Strict mode: also redact IPs and emails
    if mode == "strict":
        result = _IP_PATTERN.sub("[REDACTED:ip]", result)
        result = _EMAIL_PATTERN.sub("[REDACTED:email]", result)

    return result


# -- Utility: hash for audit trail ---------------------------------------------


def content_fingerprint(data: dict[str, Any]) -> str:
    """
    Generate a deterministic fingerprint of data for audit correlation.

    The fingerprint allows correlating redacted LangSmith traces with
    unredacted Kai-internal telemetry without exposing content.
    """
    import json

    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
