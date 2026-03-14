from __future__ import annotations


def test_scope_validator_sync_uses_workflow_scope(monkeypatch):
    import apps.backend.src.core.authorization_gate as authorization_gate

    called = {"count": 0}

    def _fake_is_in_scope(target: str, workflow_id: str | None = None) -> bool:
        called["count"] += 1
        assert target == "api.example.com"
        assert workflow_id == "wf-123"
        return True

    monkeypatch.setattr(
        authorization_gate,
        "is_in_scope_for_workflow",
        _fake_is_in_scope,
    )

    assert (
        authorization_gate.scope_validator(
            "https://api.example.com/path",
            program_id="program-1",
            method="tool_execution",
            workflow_id="wf-123",
        )
        is True
    )
    assert called["count"] == 1


def test_scope_validator_sync_falls_back_to_static_policy_without_workflow(monkeypatch):
    import apps.backend.src.core.authorization_gate as authorization_gate
    from apps.backend.src.core.scope_guardrails import ScopePolicy

    monkeypatch.setattr(
        authorization_gate,
        "load_scope_policy",
        lambda: ScopePolicy(strict_allowlist=True),
    )

    assert (
        authorization_gate.scope_validator(
            "api.example.com",
            program_id="program-1",
            method="tool_execution",
            workflow_id=None,
        )
        is False
    )
