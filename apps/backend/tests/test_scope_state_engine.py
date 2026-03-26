from __future__ import annotations

from apps.backend.src.core.scope_state_engine import ScopeStateEngine


def test_scope_state_engine_detects_and_persists_deltas(tmp_path):
    state_file = tmp_path / "scope_state.json"
    engine = ScopeStateEngine(state_file)
    engine.load()

    baseline = [
        {"id": "a1", "url": "https://a.example.com", "type": "asset"},
        {"id": "a2", "url": "https://b.example.com", "type": "asset"},
    ]
    first_delta = engine.identify_new_opportunities(baseline)
    assert len(first_delta) == 2
    assert engine.known_count() == 2

    engine.begin_scan(scan_id="scan-1", metadata={"source": "unit-test"})
    engine.mark_page(source="program_api", page_number=1, item_count=2)
    engine.save()

    resumed = ScopeStateEngine(state_file)
    resumed.load()
    second_delta = resumed.identify_new_opportunities(
        [
            {"id": "a2", "url": "https://b.example.com", "type": "asset"},
            {"id": "a3", "url": "https://c.example.com", "type": "asset"},
        ]
    )
    assert [row["id"] for row in second_delta] == ["a3"]
    assert resumed.known_count() == 3
