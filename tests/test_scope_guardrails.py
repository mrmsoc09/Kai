from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from apps.backend.src.core.scope_guardrails import (
    ScopeDecision,
    ScopePolicy,
    audit_scope_decision,
    default_scope_policy_path,
    enforce_safe_mode_for_tool,
    enforce_target_in_scope,
    evaluate_target_scope,
    load_scope_policy,
    target_scope_decision,
)


def test_scope_allowlist_and_denylist():
    policy = ScopePolicy(allowlist=["*.example.com"], denylist=["admin.example.com"])
    assert target_scope_decision("api.example.com", policy) == (True, "allowlist_match")
    assert target_scope_decision("admin.example.com", policy) == (False, "denylist_match")
    assert target_scope_decision("other.org", policy) == (False, "allowlist_no_match")


def test_safe_mode_enforcement_blocks_intrusive():
    with pytest.raises(ValueError):
        enforce_safe_mode_for_tool(
            "ffuf",
            safe_mode=True,
            tool_entry={"safety_classification": "intrusive"},
        )


def test_safe_mode_enforcement_blocks_manual_only():
    with pytest.raises(ValueError):
        enforce_safe_mode_for_tool(
            "sqlmap",
            safe_mode=True,
            tool_entry={"safety_classification": "manual_only"},
        )


def test_safe_mode_allows_passive_tools():
    # should not raise
    enforce_safe_mode_for_tool("subfinder", safe_mode=True, tool_entry={"safety_classification": "passive"})


def test_safe_mode_disabled_allows_intrusive():
    # should not raise when safe_mode=False
    enforce_safe_mode_for_tool("ffuf", safe_mode=False, tool_entry={"safety_classification": "intrusive"})


def test_enforce_target_in_scope_raises():
    policy = ScopePolicy(allowlist=["example.com"], strict_allowlist=True)
    with pytest.raises(ValueError):
        enforce_target_in_scope("evil.com", policy)


def test_empty_target_is_rejected():
    policy = ScopePolicy()
    allowed, reason = target_scope_decision("", policy)
    assert allowed is False
    assert reason == "invalid_target"


def test_denylist_takes_priority_over_allowlist():
    policy = ScopePolicy(allowlist=["*.example.com"], denylist=["*.example.com"])
    allowed, reason = target_scope_decision("api.example.com", policy)
    assert allowed is False
    assert reason == "denylist_match"


def test_cidr_allowlist_match():
    policy = ScopePolicy(cidr_allowlist=["192.168.1.0/24"])
    allowed, reason = target_scope_decision("192.168.1.50", policy)
    assert allowed is True
    assert reason == "cidr_allowlist_match"


def test_cidr_denylist_still_blocks_ip():
    policy = ScopePolicy(denylist=["192.168.1.50"], cidr_allowlist=["192.168.1.0/24"])
    allowed, reason = target_scope_decision("192.168.1.50", policy)
    assert allowed is False
    assert reason == "denylist_match"


def test_strict_allowlist_without_entries_blocks_all():
    policy = ScopePolicy(strict_allowlist=True)
    allowed, reason = target_scope_decision("anything.com", policy)
    assert allowed is False
    assert reason == "strict_allowlist_without_entries"


def test_url_target_is_normalized_to_host():
    policy = ScopePolicy(allowlist=["example.com"])
    allowed, reason = target_scope_decision("https://example.com/path?q=1", policy)
    assert allowed is True


def test_wildcard_subdomain_pattern():
    policy = ScopePolicy(allowlist=["*.example.com"])
    assert target_scope_decision("sub.example.com", policy) == (True, "allowlist_match")
    assert target_scope_decision("example.com", policy) == (False, "allowlist_no_match")


def test_glob_pattern_in_allowlist():
    # Task 23: regex /pattern/ syntax replaced with fnmatch glob for security
    policy = ScopePolicy(allowlist=["*.example.com"])
    allowed, _ = target_scope_decision("api.example.com", policy)
    assert allowed is True


def test_glob_pattern_does_not_match_cross_boundary():
    # *.example.com must NOT match evilexample.com (dot boundary enforcement)
    policy = ScopePolicy(allowlist=["*.example.com"])
    allowed, reason = target_scope_decision("evilexample.com", policy)
    assert allowed is False


def test_load_scope_policy_from_yaml(tmp_path):
    cfg = tmp_path / "policy.yaml"
    cfg.write_text("allowlist:\n  - '*.example.com'\ndenylist:\n  - 'admin.example.com'\n")
    policy = load_scope_policy(cfg)
    assert "*.example.com" in policy.allowlist
    assert "admin.example.com" in policy.denylist


def test_load_scope_policy_missing_file_returns_defaults():
    policy = load_scope_policy("/nonexistent/path/policy.yaml")
    assert policy.safe_mode_default is True
    assert policy.allowlist == []


def test_load_scope_policy_malformed_yaml_returns_defaults(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("- just\n- a\n- list\n")
    policy = load_scope_policy(cfg)
    assert policy.allowlist == []


def test_audit_scope_decision_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_WORKFLOW_OUTPUT_ROOT", str(tmp_path))
    decision = evaluate_target_scope("api.example.com", ScopePolicy(allowlist=["*.example.com"]))
    audit_scope_decision(decision)
    log_path = tmp_path / "logs" / "scope_decisions.jsonl"
    assert log_path.exists()
    lines = [json.loads(ln) for ln in log_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    assert lines[0]["target"] == "api.example.com"
    assert lines[0]["allowed"] is True


def test_audit_scope_decision_appends_multiple(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_WORKFLOW_OUTPUT_ROOT", str(tmp_path))
    policy = ScopePolicy(allowlist=["*.example.com"])
    for host in ("a.example.com", "b.example.com", "c.example.com"):
        audit_scope_decision(evaluate_target_scope(host, policy))
    log_path = tmp_path / "logs" / "scope_decisions.jsonl"
    lines = log_path.read_text().splitlines()
    assert len(lines) == 3


def test_policy_default_allow_when_no_allowlist_and_not_strict():
    policy = ScopePolicy()  # no allowlist, not strict
    allowed, reason = target_scope_decision("anything.com", policy)
    assert allowed is True
    assert reason == "policy_default_allow"


def test_repo_default_scope_policy_is_deny_by_default():
    policy = load_scope_policy(default_scope_policy_path())
    assert policy.strict_allowlist is True
    allowed, reason = target_scope_decision("unlisted.example.org", policy)
    assert allowed is False
    assert reason in {"allowlist_no_match", "strict_allowlist_without_entries"}
