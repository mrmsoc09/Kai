"""
Workflow-Aware Scope Resolver

Supplements the static policies.yaml scope list with dynamic scope derived
from active hunt workflows.  When a workflow exists for the target being
scanned, its scope_domains list is treated as the authoritative allow-list,
bypassing the need to manually maintain policies.yaml for every program.

Priority order:
  1. Explicit deny in policies.yaml (always respected)
  2. Match in active workflow scope_domains  <- new dynamic path
  3. Match in static allowed_scopes from policies.yaml

This resolves the critical gap where only *.adobe.com was ever accepted by
the scope gate, blocking all tool execution for every other program.
"""

from __future__ import annotations

import re
from typing import Optional


def _host_matches_pattern(host: str, pattern: str) -> bool:
    """Return True if host matches a scope_domains entry.

    Patterns:
      *.shopify.com  -> wildcard subdomain match
      shopify.com    -> exact host match
      /regex/        -> interpreted as a regex
    """
    pattern = pattern.strip()
    if not pattern:
        return False

    if len(pattern) >= 2 and pattern[0] == "/" and pattern[-1] == "/":
        try:
            return bool(re.search(pattern[1:-1], host, re.IGNORECASE))
        except re.error:
            return False

    if "*" in pattern:
        glob_rx = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.search(glob_rx + "$", host, re.IGNORECASE))

    return host.lower() == pattern.lower()


def _target_in_any_active_workflow(host: str, workflow_id: Optional[str] = None) -> bool:
    """Return True if host matches any scope_domain in an active workflow."""
    try:
        from .workflow_store import list_workflows, get_workflow
    except Exception:
        return False

    try:
        if workflow_id:
            wf = get_workflow(workflow_id)
            workflows = [wf] if wf and not wf.is_terminal() else []
        else:
            workflows = [w for w in list_workflows() if not w.is_terminal()]

        for wf in workflows:
            for pattern in wf.scope_domains:
                if _host_matches_pattern(host, pattern):
                    return True
    except Exception:
        pass

    return False


def is_in_scope_for_workflow(target: str, workflow_id: Optional[str] = None) -> bool:
    """
    Check whether target is in scope via:
      1. Global deny list from policies.yaml
      2. Active workflow scope_domains (dynamic)
      3. Static allowed_scopes from policies.yaml
    """
    from .scope import _DENY_RX, _ALLOWED_RX, _extract_host_or_text

    host = _extract_host_or_text(target)
    if not host:
        return False

    if any(rx.search(host) for rx in _DENY_RX):
        return False

    if _target_in_any_active_workflow(host, workflow_id):
        return True

    return bool(_ALLOWED_RX and any(rx.search(host) for rx in _ALLOWED_RX))


def get_scope_context(target: str) -> dict:
    """Return full scope context for a target — used for audit logging and
    injecting workflow_id into tool params at dispatch time."""
    from .scope import _DENY_RX, _ALLOWED_RX, _extract_host_or_text

    host = _extract_host_or_text(target)

    if any(rx.search(host) for rx in _DENY_RX):
        return {"in_scope": False, "source": "deny_list", "workflow_id": None, "host": host}

    try:
        from .workflow_store import list_workflows
        for wf in list_workflows():
            if wf.is_terminal():
                continue
            for pattern in wf.scope_domains:
                if _host_matches_pattern(host, pattern):
                    return {
                        "in_scope": True,
                        "source": "workflow",
                        "workflow_id": wf.id,
                        "opportunity_id": wf.opportunity_id,
                        "program_name": wf.program_name,
                        "host": host,
                    }
    except Exception:
        pass

    if _ALLOWED_RX and any(rx.search(host) for rx in _ALLOWED_RX):
        return {"in_scope": True, "source": "policy", "workflow_id": None, "host": host}

    return {"in_scope": False, "source": "no_match", "workflow_id": None, "host": host}
