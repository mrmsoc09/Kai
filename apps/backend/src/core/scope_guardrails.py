from __future__ import annotations

import ipaddress
import json
import re
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


import yaml

from .helpers import repo_root, utcnow, workflow_output_root

_AUDIT_LOCK = threading.Lock()


@dataclass
class ScopePolicy:
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    cidr_allowlist: list[str] = field(default_factory=list)
    safe_mode_default: bool = True
    strict_allowlist: bool = False


@dataclass
class ScopeDecision:
    target: str
    normalized_host: str
    allowed: bool
    reason: str
    matched_rule: str | None = None
    safe_mode: bool | None = None
    evaluated_at: str = field(default_factory=lambda: utcnow().isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_scope_policy_path() -> Path:
    return repo_root() / "config" / "scope_guardrails.yaml"


def load_scope_policy(path: str | Path | None = None) -> ScopePolicy:
    cfg_path = Path(path).expanduser().resolve() if path else default_scope_policy_path()
    if not cfg_path.exists():
        return ScopePolicy()
    payload = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return ScopePolicy()
    return ScopePolicy(
        allowlist=[str(item).strip() for item in payload.get("allowlist", []) if str(item).strip()],
        denylist=[str(item).strip() for item in payload.get("denylist", []) if str(item).strip()],
        cidr_allowlist=[
            str(item).strip() for item in payload.get("cidr_allowlist", []) if str(item).strip()
        ],
        safe_mode_default=bool(payload.get("safe_mode_default", True)),
        strict_allowlist=bool(payload.get("strict_allowlist", False)),
    )


def _to_host(value: str) -> str:
    value = (value or "").strip().lower()
    if not value:
        return ""
    if "://" in value:
        parsed = urlparse(value)
        return (parsed.hostname or "").strip().lower()
    return value.split("/")[0]


def _pattern_matches(host: str, pattern: str) -> bool:
    pattern = pattern.lower().strip()
    if not pattern:
        return False
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return host.endswith(suffix)
    if pattern.startswith("/") and pattern.endswith("/") and len(pattern) > 2:
        try:
            return re.search(pattern[1:-1], host, flags=re.IGNORECASE) is not None
        except re.error:
            return False
    return host == pattern or host.endswith(f".{pattern}")


def _host_is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _ip_in_allowlisted_cidr(host: str, cidrs: list[str]) -> bool:
    if not _host_is_ip(host):
        return False
    ip = ipaddress.ip_address(host)
    for cidr in cidrs:
        try:
            if ip in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def target_scope_decision(target: str, policy: ScopePolicy) -> tuple[bool, str]:
    decision = evaluate_target_scope(target, policy)
    return decision.allowed, decision.reason


def evaluate_target_scope(target: str, policy: ScopePolicy, *, safe_mode: bool | None = None) -> ScopeDecision:
    host = _to_host(target)
    if not host:
        return ScopeDecision(
            target=target,
            normalized_host=host,
            allowed=False,
            reason="invalid_target",
            safe_mode=safe_mode,
        )

    for denied in policy.denylist:
        if _pattern_matches(host, denied):
            return ScopeDecision(
                target=target,
                normalized_host=host,
                allowed=False,
                reason="denylist_match",
                matched_rule=denied,
                safe_mode=safe_mode,
            )

    if _ip_in_allowlisted_cidr(host, policy.cidr_allowlist):
        return ScopeDecision(
            target=target,
            normalized_host=host,
            allowed=True,
            reason="cidr_allowlist_match",
            matched_rule=host,
            safe_mode=safe_mode,
        )

    if policy.allowlist:
        for allowed in policy.allowlist:
            if _pattern_matches(host, allowed):
                return ScopeDecision(
                    target=target,
                    normalized_host=host,
                    allowed=True,
                    reason="allowlist_match",
                    matched_rule=allowed,
                    safe_mode=safe_mode,
                )
        return ScopeDecision(
            target=target,
            normalized_host=host,
            allowed=False,
            reason="allowlist_no_match",
            safe_mode=safe_mode,
        )

    if policy.strict_allowlist:
        return ScopeDecision(
            target=target,
            normalized_host=host,
            allowed=False,
            reason="strict_allowlist_without_entries",
            safe_mode=safe_mode,
        )

    return ScopeDecision(
        target=target,
        normalized_host=host,
        allowed=True,
        reason="policy_default_allow",
        safe_mode=safe_mode,
    )


def _scope_audit_log_path() -> Path:
    log_dir = workflow_output_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "scope_decisions.jsonl"


def audit_scope_decision(decision: ScopeDecision) -> None:
    path = _scope_audit_log_path()
    entry = json.dumps(decision.as_dict(), default=str) + "\n"
    with _AUDIT_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)


def enforce_target_in_scope(target: str, policy: ScopePolicy) -> None:
    decision = evaluate_target_scope(target, policy)
    audit_scope_decision(decision)
    if not decision.allowed:
        raise ValueError(f"Target '{target}' is out of scope ({decision.reason})")


def enforce_safe_mode_for_tool(tool_name: str, safe_mode: bool, tool_entry: dict[str, Any] | None = None) -> None:
    if not safe_mode:
        return
    if tool_entry and str(tool_entry.get("safety_classification", "")).lower() in {
        "intrusive",
        "manual_only",
    }:
        raise ValueError(
            f"Tool '{tool_name}' is blocked in safe_mode due to safety classification "
            f"{tool_entry.get('safety_classification')}"
        )
