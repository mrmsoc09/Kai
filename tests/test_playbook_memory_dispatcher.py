from __future__ import annotations

import json
from pathlib import Path

from apps.backend.src.core.orchestrator_dispatcher import OrchestratorDispatcher
from apps.backend.src.core.playbook_memory import PlaybookMemory
from apps.backend.src.core.tools import (
    BaseTool,
    ToolAutonomyTier,
    ToolCategory,
    ToolResult,
    ToolStatus,
)


class _FakeTool(BaseTool):
    def __init__(self, tool_id: str):
        super().__init__(
            id=tool_id,
            name=tool_id,
            description="fake",
            category=ToolCategory.ORCHESTRATION,
            autonomy_tier=ToolAutonomyTier.TIER_0_AUTO,
            parameters=[],
        )

    def execute(self, headers=None, **kwargs):
        return ToolResult(
            tool_id=self.id,
            status=ToolStatus.COMPLETED,
            output={"echo": kwargs},
            metadata={"exit_code": 0},
        )


class _FakeRegistry:
    def __init__(self):
        self._tools = {"tool.alpha": _FakeTool("tool.alpha"), "tool.beta": _FakeTool("tool.beta")}

    def get(self, tool_id: str):
        return self._tools.get(tool_id)


def _write_index_files(tmp_path: Path) -> tuple[Path, Path]:
    playbook_root = tmp_path / "tools" / "playbooks"
    chain_dir = playbook_root / "chain_orchestration"
    chain_dir.mkdir(parents=True)

    (chain_dir / "cve_index.json").write_text(
        json.dumps(
            {
                "CVE-2026-1111": [
                    {"playbook_id": "pb.auth", "cvss_score": 9.1, "severity": "HIGH"},
                    {"playbook_id": "pb.info", "cvss_score": 5.2, "severity": "MEDIUM"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (chain_dir / "prerequisite_index.json").write_text(
        json.dumps(
            {
                "nginx": [{"playbook_id": "pb.auth"}],
                "httpx_probe": [{"playbook_id": "pb.info"}],
            }
        ),
        encoding="utf-8",
    )
    (chain_dir / "execution_plan_cache.json").write_text(
        json.dumps(
            {
                "pb.auth": [
                    [1, "pb.auth", {"tool_id": "tool.alpha"}, {"timeout_seconds": 30}, "tool.beta"]
                ]
            }
        ),
        encoding="utf-8",
    )
    (chain_dir / "data_contract_registry.json").write_text(
        json.dumps(
            {
                "contracts": [
                    {"output_schema": "ServiceRegistry", "input_schema": "VulnerabilityRegistry"}
                ]
            }
        ),
        encoding="utf-8",
    )
    (playbook_root / "playbook_index.json").write_text(
        json.dumps(
            {
                "playbooks_by_success_weight": [
                    {
                        "id": "pb.auth",
                        "name": "Auth Path",
                        "success_weight": 0.8,
                        "category": "Exploitation",
                        "tools": ["tool.alpha", "tool.beta"],
                        "tags": ["auth"],
                        "prerequisites": ["nginx"],
                    },
                    {
                        "id": "pb.info",
                        "name": "Info Path",
                        "success_weight": 0.2,
                        "category": "Recon",
                        "tools": ["tool.beta"],
                        "tags": ["info"],
                        "prerequisites": ["httpx_probe"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return playbook_root, chain_dir


def test_playbook_memory_fast_lookup_and_contracts(tmp_path: Path) -> None:
    playbook_root, chain_dir = _write_index_files(tmp_path)
    memory = PlaybookMemory(chain_orchestration_dir=chain_dir, playbook_root=playbook_root)

    ranked = memory.match_target_to_playbook("CVE-2026-1111", ["nginx"])
    assert ranked
    assert ranked[0]["playbook_id"] == "pb.auth"
    assert memory.validate_handoff("ServiceRegistry", "VulnerabilityRegistry") is True
    assert memory.validate_handoff("DiscoveryRegistry", "XssRegistry") is False


def test_orchestrator_dispatcher_executes_instruction_tuples(tmp_path: Path) -> None:
    playbook_root, chain_dir = _write_index_files(tmp_path)
    memory = PlaybookMemory(chain_orchestration_dir=chain_dir, playbook_root=playbook_root)
    dispatcher = OrchestratorDispatcher(playbook_memory=memory, registry=_FakeRegistry())

    out = dispatcher.dispatch_cached_plan(key="pb.auth", target="example.com")
    assert out
    assert out[0]["status"] == "completed"
    assert out[0]["tool_id"] == "tool.alpha"
    assert out[0]["output"]["output"]["echo"]["target"] == "example.com"

