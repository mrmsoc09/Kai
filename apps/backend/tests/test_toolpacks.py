from __future__ import annotations

from pathlib import Path

import pytest

from apps.backend.src.core.toolpacks import ToolpackManager, ToolpackValidationError


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_toolpacks_resolve_enabled_mappings(tmp_path: Path):
    config = _write(
        tmp_path / "toolpacks.yaml",
        """
schema_version: "1.0"
platform:
  primary_os: ["debian13"]
  compatible_os: ["kali"]
  tools_root: "/opt/tools"
  artifacts_root: "/opt/artifacts"
  cache_root: "/opt/cache"
toolpacks:
  recon:
    description: "recon"
    enabled: true
    tools:
      - id: "httpx"
        adapter_id: "httpx_probe"
        method: "http_probe"
        evidence_type: "http"
      - id: "gau"
        adapter_id: "gau_adapter"
        enabled: false
        method: "endpoint_discovery"
        evidence_type: "crawl"
""",
    )

    manager = ToolpackManager(config)
    manager.load()
    mappings = manager.resolve_mappings({"httpx_probe"})

    assert mappings == {"httpx": "httpx_probe"}
    assert manager.is_adapter_enabled("httpx_probe") is True
    assert manager.is_adapter_enabled("gau_adapter") is False


def test_toolpacks_fail_closed_on_unresolved_enabled_mapping(tmp_path: Path):
    config = _write(
        tmp_path / "toolpacks.yaml",
        """
schema_version: "1.0"
platform:
  primary_os: ["debian13"]
  compatible_os: ["kali"]
  tools_root: "/opt/tools"
  artifacts_root: "/opt/artifacts"
  cache_root: "/opt/cache"
toolpacks:
  recon:
    description: "recon"
    enabled: true
    tools:
      - id: "dnsx"
        adapter_id: "dnsx_adapter"
        method: "dns_enum"
        evidence_type: "dns"
""",
    )

    manager = ToolpackManager(config)
    manager.load()
    with pytest.raises(ToolpackValidationError, match="unresolved toolpack adapter mappings"):
        manager.resolve_mappings({"subfinder"})


def test_toolpack_env_override_disable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    config = _write(
        tmp_path / "toolpacks.yaml",
        """
schema_version: "1.0"
platform:
  primary_os: ["debian13"]
  compatible_os: ["kali"]
  tools_root: "/opt/tools"
  artifacts_root: "/opt/artifacts"
  cache_root: "/opt/cache"
toolpacks:
  recon:
    description: "recon"
    enabled: true
    tools:
      - id: "subfinder"
        adapter_id: "subfinder"
        method: "dns_enum"
        evidence_type: "dns"
""",
    )

    monkeypatch.setenv("K1_TOOLPACKS_DISABLE", "recon")
    manager = ToolpackManager(config)
    manager.load()
    mappings = manager.resolve_mappings({"subfinder"})

    assert mappings == {}
