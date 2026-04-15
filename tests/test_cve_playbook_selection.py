from __future__ import annotations

from pathlib import Path

import yaml

from apps.backend.src.core.cve_playbook_selector import CVEPlaybookSelector
from apps.backend.src.core.master_orchestrator import MasterOrchestrator


def _write_fixture_files(tmp_path: Path) -> tuple[Path, Path]:
    cve_path = tmp_path / "cve_knowledge.yaml"
    cve_path.write_text(
        yaml.safe_dump(
            {
                "cve_index": {
                    "CVE-2024-9999": {
                        "metadata": {
                            "cve_id": "CVE-2024-9999",
                            "cvss_score": 9.8,
                            "severity": "CRITICAL",
                        },
                        "vulnerability": {
                            "product": "Nginx",
                            "affected_versions": ["1.18.0"],
                            "vulnerability_type": "Auth Bypass",
                        },
                        "persona_mapping": {
                            "playbooks": [
                                {"playbook": "auth_bypass_v1"},
                            ],
                            "relevant_personas": [{"persona": "auth_tester"}],
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    playbook_path = tmp_path / "playbook_registry.yaml"
    playbook_path.write_text(
        yaml.safe_dump(
            {
                "playbook_registry": {
                    "playbooks": [
                        {
                            "id": "auth_bypass_v1",
                            "name": "Authentication Bypass",
                            "path": "tools/playbooks/exploitation/auth_bypass.yaml",
                            "tags": ["authentication", "auth-bypass", "api-security"],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return cve_path, playbook_path


def test_selector_maps_service_signal_to_playbook(tmp_path: Path) -> None:
    cve_path, playbook_path = _write_fixture_files(tmp_path)
    selector = CVEPlaybookSelector(
        cve_knowledge_path=str(cve_path),
        playbook_registry_path=str(playbook_path),
    )
    selection = selector.select_for_signals(
        signals=[{"service": "nginx 1.18.0", "source_tool": "nmap"}],
        prioritized_findings=[],
    )
    assert selection["cve_matches"]
    assert selection["cve_matches"][0]["cve_id"] == "CVE-2024-9999"
    assert selection["playbook_recommendations"]
    assert selection["playbook_recommendations"][0]["playbook_id"] == "auth_bypass_v1"


def test_master_orchestrator_bridge_selection(tmp_path: Path) -> None:
    cve_path, playbook_path = _write_fixture_files(tmp_path)

    orchestrator = MasterOrchestrator()
    # Inject fixture selector for deterministic test behavior.
    orchestrator._selector = CVEPlaybookSelector(
        cve_knowledge_path=str(cve_path),
        playbook_registry_path=str(playbook_path),
    )

    result = orchestrator.select_playbooks_for_discovery(
        service_findings=[{"technology": "Nginx 1.18.0", "source_tool": "httpx_probe"}]
    )
    payload = result.as_dict()
    assert payload["matched_cves"]
    assert payload["recommendations"]
    assert payload["chain_plan"] == ["auth_bypass_v1"]

