from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from apps.backend.src.agents.tools.reconftw.agent import ReconftwAgent, ReconftfwAgent
from apps.backend.src.agents.tools.reconftw.reconftw_config import (
    build_reconftw_cfg_content,
    write_reconftw_cfg,
)


def _make_scope_policy(tmp_path: Path) -> Path:
    policy_path = tmp_path / "scope_guardrails.yaml"
    policy_path.write_text(
        yaml.safe_dump(
            {
                "allowlist": ["example.com"],
                "denylist": [],
                "cidr_allowlist": [],
                "safe_mode_default": True,
                "strict_allowlist": False,
            }
        ),
        encoding="utf-8",
    )
    return policy_path


def _metric_values(events: list[dict[str, Any]], metric: str) -> list[Any]:
    return [e.get("value") for e in events if e.get("metric") == metric]


def test_reconftw_cfg_generation_includes_snl_and_conflict_controls(tmp_path: Path) -> None:
    content = build_reconftw_cfg_content(
        target="example.com",
        snl_settings={
            "allowed_interfaces": ["tun0", "wg0"],
            "active_interface": "tun0",
            "proxy_url": "socks5://127.0.0.1:9050",
            "use_proxies": True,
        },
        nvme_root="/mnt/nvme",
        output_root=str(tmp_path / "output"),
    )
    assert "K1_SNL_ALLOWED_INTERFACES=tun0,wg0" in content
    assert "K1_DISABLE_MANAGED_TOOLS=amass,findomain,httpx,naabu,nuclei,subfinder" in content
    assert "K1_RECONFTW_SELECTIVE_MODE=true" in content


def test_write_reconftw_cfg_creates_file(tmp_path: Path) -> None:
    cfg_path = tmp_path / "reconftw.cfg"
    result = write_reconftw_cfg(target="example.com", config_path=cfg_path)
    assert cfg_path.exists()
    assert result.config_path.endswith("reconftw.cfg")
    assert "K1_TARGET=example.com" in cfg_path.read_text(encoding="utf-8")


def test_reconftw_build_command_selective_modes(tmp_path: Path) -> None:
    agent = ReconftwAgent(memory_root=tmp_path / "memory")
    cmd = agent.build_command(
        "example.com",
        {
            "mode": "web",
            "output_dir": str(tmp_path / "out"),
            "config_path": str(tmp_path / "reconftw.cfg"),
            "timeout_seconds": 900,
        },
    )
    assert cmd[0] in {"reconftw", "reconftw.sh"}
    assert "--web" in cmd
    assert "--subdomains" not in cmd
    assert "-c" in cmd and str(tmp_path / "reconftw.cfg") in cmd


def test_reconftw_directory_ingestion_maps_discovery_and_inventory(tmp_path: Path) -> None:
    agent = ReconftwAgent(memory_root=tmp_path / "memory")
    out_dir = tmp_path / "recon-output"
    (out_dir / "subdomains").mkdir(parents=True)
    (out_dir / "web").mkdir(parents=True)
    (out_dir / "providers").mkdir(parents=True)
    (out_dir / "screenshots").mkdir(parents=True)

    (out_dir / "subdomains" / "subdomains.txt").write_text("api.example.com\n", encoding="utf-8")
    (out_dir / "subdomains" / "ips.txt").write_text("1.2.3.4\n", encoding="utf-8")
    (out_dir / "web" / "alive.txt").write_text("https://api.example.com\n", encoding="utf-8")
    (out_dir / "providers" / "cloud.txt").write_text("aws:us-east-1\n", encoding="utf-8")
    (out_dir / "screenshots" / "api.example.com.png").write_bytes(b"png")

    findings = agent.parse_output_directory(out_dir, "example.com")
    values = {f["value"] for f in findings}
    assert "api.example.com" in values
    assert "1.2.3.4" in values
    assert "https://api.example.com" in values
    assert any("asset_inventory_registry" in f.get("context", {}) for f in findings)
    assert any("discovery_registry" in f.get("context", {}) for f in findings)


def test_reconftw_execute_phase_handshake_and_telemetry(tmp_path: Path) -> None:
    agent = ReconftwAgent(memory_root=tmp_path / "memory")
    scope_policy = _make_scope_policy(tmp_path)
    hook_calls: list[dict[str, Any]] = []

    def _phase_hook(payload: dict[str, Any]) -> dict[str, Any]:
        hook_calls.append(payload)
        return {"cross_reference": "ok"}

    result = agent.execute(
        "example.com",
        {
            "scope_policy_path": str(scope_policy),
            "fixture_data": "found api.example.com in passive sources\nhttps://api.example.com\n",
            "snl_interface": "tun0",
            "modes": ["subdomains", "web"],
            "phase_hook": _phase_hook,
        },
    )
    assert result.status == "success"
    assert len(hook_calls) == 2
    assert result.target_context.get("selective_modes") == ["subdomains", "web"]
    telemetry = result.target_context.get("telemetry", [])
    assert _metric_values(telemetry, "TOTAL_ASSETS_MAPPED") == [len(result.findings)]
    assert _metric_values(telemetry, "EventLog") == ["SATELLITE_SWEEP_LARGE_ARCS"]


def test_reconftw_install_plan_contains_conflict_resolution(tmp_path: Path) -> None:
    agent = ReconftwAgent(memory_root=tmp_path / "memory")
    install = agent.install(
        target="example.com",
        options={
            "output_root": str(tmp_path / "output"),
            "nvme_root": str(tmp_path / "nvme"),
            "k1_vpn_allowed_interfaces": "tun0,wg0",
        },
    )
    assert install["conflict_resolution"]["reconftw_autoinstall_disabled"] is True
    assert "nuclei" in install["managed_tools_disabled"]
    assert Path(install["config_path"]).exists()
    assert isinstance(install["install_commands"], list) and install["install_commands"]


def test_reconftfw_alias_remains_available(tmp_path: Path) -> None:
    agent = ReconftfwAgent(memory_root=tmp_path / "memory")
    assert agent.TOOL_NAME == "reconftw"
