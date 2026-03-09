from ai_kernel.governance.hooks import session_init, scope_guard, tool_filter, result_normalizer, quality_gate


def test_session_init_basic():
    res = session_init.run({"request_id": "r1"})
    assert res.ok


def test_scope_guard_requires_flags():
    res = scope_guard.run({"tool_id": "t", "adapter_id": "a"})
    assert res.ok is False


def test_tool_filter_adapter_required():
    res = tool_filter.run({"args": {}})
    assert res.ok is False


def test_quality_gate_needs_evidence():
    res = quality_gate.run({"evidence_ids": []})
    assert res.ok is False
