from __future__ import annotations
from fastapi import Header, HTTPException
from pathlib import Path
from typing import Any, Dict, List
import os, re
from .scope_guardrails import evaluate_target_scope, load_scope_policy

ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / 'config' / 'policies.yaml'

_POLICY: Dict[str, Any] = {
    'allowed_scopes': [],   # list of patterns or regex; default empty means deny unless header override
    'deny_scopes': [],      # optional explicit denies
}

try:
    import yaml  # type: ignore
except Exception:  # fallback if PyYAML missing
    yaml = None


def _compile_patterns(patterns: List[str]) -> List[re.Pattern]:
    compiled: List[re.Pattern] = []
    for pat in patterns or []:
        pat = pat.strip()
        if not pat:
            continue
        # If looks like a regex (/.../), strip slashes and compile as-is
        if len(pat) >= 2 and pat[0] == '/' and pat[-1] == '/':
            try:
                compiled.append(re.compile(pat[1:-1], re.IGNORECASE))
                continue
            except re.error:
                continue
        # Glob-like to regex: escape and replace * with .*
        r = re.escape(pat).replace(r'\*', '.*')
        compiled.append(re.compile(r + '$', re.IGNORECASE))
    return compiled


_ALLOWED_RX: List[re.Pattern] = []
_DENY_RX: List[re.Pattern] = []


def reload_policies() -> Dict[str, Any]:
    global _POLICY, _ALLOWED_RX, _DENY_RX
    data: Dict[str, Any] = dict(_POLICY)
    if CONFIG.exists() and yaml:
        try:
            data = yaml.safe_load(CONFIG.read_text()) or data
        except Exception:
            pass
    _POLICY = data
    _ALLOWED_RX = _compile_patterns(list(_POLICY.get('allowed_scopes') or []))
    _DENY_RX = _compile_patterns(list(_POLICY.get('deny_scopes') or []))
    return _POLICY


# Initialize on import
reload_policies()


def _extract_host_or_text(value: str) -> str:
    if not value:
        return ''
    v = value.strip()
    # naive URL host extraction
    m = re.match(r'^[a-z][a-z0-9+.-]*://([^/]+)', v, re.I)
    if m:
        return m.group(1)
    return v


def is_in_scope(value: str) -> bool:
    # Canonical scope authority is scope_guardrails.
    # Keep this helper as a compatibility bridge for legacy routers.
    policy = load_scope_policy()
    decision = evaluate_target_scope(_extract_host_or_text(value), policy)
    return decision.allowed


# Simple, explicit scope acceptance check dependency for execute-mode
async def require_scope_accept(x_accept_scope: str | None = Header(default=None)):
    # Allow local override for automation tests
    if os.environ.get('ACCEPT_SCOPE') == '1':
        return True
    if (x_accept_scope or '').strip() == '1':
        return True
    raise HTTPException(403, 'Scope acceptance required: send header X-Accept-Scope: 1')
