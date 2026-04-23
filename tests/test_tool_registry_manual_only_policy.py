from __future__ import annotations

from apps.backend.src.core.tool_registry_catalog import list_catalog_entries


def test_manual_only_entries_are_disabled_and_wrapper_pending():
    entries = [
        entry
        for entry in list_catalog_entries(enabled_only=False)
        if entry.safety_classification == "manual_only"
    ]

    assert entries, "Expected at least one manual_only entry in the tool catalog"

    for entry in entries:
        assert entry.enabled_by_default is False, (
            f"{entry.name} must be disabled by default when marked manual_only"
        )
        assert entry.execution_mode == "optional", (
            f"{entry.name} must use execution_mode=optional when marked manual_only"
        )
        assert "wrapper_pending" in entry.dependencies, (
            f"{entry.name} must declare wrapper_pending dependency"
        )
