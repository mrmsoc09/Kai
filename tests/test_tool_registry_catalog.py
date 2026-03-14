from __future__ import annotations

from apps.backend.src.core.tool_registry_catalog import (
    get_catalog_entry,
    list_catalog_entries,
)


def test_catalog_contains_required_core_tools():
    names = {entry.name for entry in list_catalog_entries(enabled_only=False)}
    required = {
        "subfinder",
        "assetfinder",
        "amass",
        "httpx",
        "naabu",
        "katana",
        "ffuf",
        "nuclei",
        "nmap",
        "dalfox",
        "sqlmap",
        "trufflehog",
    }
    assert required.issubset(names)


def test_catalog_entry_shape():
    entry = get_catalog_entry("subfinder")
    assert entry is not None
    assert entry.timeout_seconds > 0
    assert entry.install_verification_cmd
    assert entry.input_schema
    assert entry.output_schema
    assert entry.retry_policy.max_attempts >= 1
