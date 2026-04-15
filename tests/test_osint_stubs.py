from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from apps.backend.src.agents.tools.osint_schemas import DiscoveryRegistry, IdentityRegistry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    module_name = f"apps.backend.src.agents.tools.{tool.replace('-', '_')}.agent_osint_stub_test"
    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {agent_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


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


def test_discovery_registry_validation() -> None:
    record = DiscoveryRegistry.model_validate(
        {
            "discovered_domain": "*.API.Example.COM.",
            "intel_source": "Chaos Dataset",
        }
    )
    assert record.discovered_domain == "api.example.com"
    assert record.intel_source == "chaos_dataset"

    with pytest.raises(ValidationError):
        DiscoveryRegistry.model_validate(
            {
                "discovered_domain": "bad domain",
                "intel_source": "chaos",
            }
        )


def test_identity_registry_validation() -> None:
    record = IdentityRegistry.model_validate(
        {
            "social_handle": "@User.Name",
            "platform_detected": "GitHub",
            "profile_url": "https://github.com/User.Name",
        }
    )
    assert record.social_handle == "User.Name"
    assert record.platform_detected == "github"

    with pytest.raises(ValidationError):
        IdentityRegistry.model_validate(
            {
                "social_handle": "bad handle with spaces",
                "platform_detected": "github",
                "profile_url": "https://github.com/example",
            }
        )


@pytest.mark.parametrize(
    ("tool", "class_name", "fixture_payload", "expected_metric", "expected_eventlog"),
    [
        (
            "chaos",
            "ChaosAgent",
            [{"domain": "api.example.com"}, {"subdomain": "admin.example.com"}],
            "PASSIVE_ASSETS_FOUND",
            "CLOUD_BURST",
        ),
        (
            "github-subdomains",
            "GithubSubdomainsAgent",
            [
                {"subdomain": "dev-api.example.com", "source": "github"},
                {"host": "internal.example.com", "source": "github"},
            ],
            "PASSIVE_ASSETS_FOUND",
            "CLOUD_BURST",
        ),
        (
            "sherlock",
            "SherlockAgent",
            {
                "profiles": [
                    {"platform": "github", "url": "https://github.com/exampleuser"},
                    {"platform": "linkedin", "url": "https://linkedin.com/in/exampleuser"},
                ]
            },
            "IDENTITY_PROFILES_FOUND",
            "PROFILE_PULSE",
        ),
        (
            "social-analyzer",
            "SocialAnalyzerAgent",
            {
                "profiles": [
                    {
                        "username": "exampleuser",
                        "platform": "github",
                        "url": "https://github.com/exampleuser",
                        "followers": 8,
                    }
                ]
            },
            "IDENTITY_PROFILES_FOUND",
            "PROFILE_PULSE",
        ),
    ],
)
def test_osint_stub_ingest_and_telemetry(
    tool: str,
    class_name: str,
    fixture_payload: str | dict[str, Any] | list[Any],
    expected_metric: str,
    expected_eventlog: str,
    tmp_path: Path,
) -> None:
    cls = _load_agent_class(tool, class_name)
    agent = cls(memory_root=tmp_path / tool / "memory")
    scope_policy_path = _make_scope_policy(tmp_path)

    records = agent.ingest_fixture(
        fixture_payload,
        target="example.com",
        options={"scope_policy_path": str(scope_policy_path)},
    )

    assert records
    telemetry = agent.get_telemetry_events()
    assert any(event.get("metric") == expected_metric for event in telemetry)
    assert any(
        event.get("metric") == "EventLog" and event.get("value") == expected_eventlog
        for event in telemetry
    )


@pytest.mark.parametrize(
    ("tool", "class_name", "fixture_payload"),
    [
        ("chaos", "ChaosAgent", [{"domain": "api.example.com"}]),
        ("github-subdomains", "GithubSubdomainsAgent", [{"subdomain": "api.example.com"}]),
        (
            "sherlock",
            "SherlockAgent",
            {"profiles": [{"platform": "github", "url": "https://github.com/exampleuser"}]},
        ),
        (
            "social-analyzer",
            "SocialAnalyzerAgent",
            {
                "profiles": [
                    {
                        "username": "exampleuser",
                        "platform": "github",
                        "url": "https://github.com/exampleuser",
                    }
                ]
            },
        ),
    ],
)
def test_osint_stub_policy_gate_blocks_unapproved_scope(
    tool: str,
    class_name: str,
    fixture_payload: str | dict[str, Any] | list[Any],
    tmp_path: Path,
) -> None:
    cls = _load_agent_class(tool, class_name)
    agent = cls(memory_root=tmp_path / tool / "memory")
    scope_policy_path = _make_scope_policy(tmp_path)

    with pytest.raises(PermissionError):
        agent.ingest_fixture(
            fixture_payload,
            target="example.com",
            options={
                "scope_policy_path": str(scope_policy_path),
                "research_scope": "Unapproved Scope",
            },
        )


@pytest.mark.parametrize(
    ("tool", "class_name", "fixture_payload"),
    [
        ("chaos", "ChaosAgent", [{"domain": "api.example.com"}]),
        ("github-subdomains", "GithubSubdomainsAgent", [{"subdomain": "dev.example.com"}]),
        (
            "sherlock",
            "SherlockAgent",
            {"profiles": [{"platform": "github", "url": "https://github.com/exampleuser"}]},
        ),
        (
            "social-analyzer",
            "SocialAnalyzerAgent",
            {
                "profiles": [
                    {
                        "username": "exampleuser",
                        "platform": "github",
                        "url": "https://github.com/exampleuser",
                        "followers": 3,
                    }
                ]
            },
        ),
    ],
)
def test_osint_stub_execute_fixture_mode(
    tool: str,
    class_name: str,
    fixture_payload: str | dict[str, Any] | list[Any],
    tmp_path: Path,
) -> None:
    cls = _load_agent_class(tool, class_name)
    agent = cls(memory_root=tmp_path / tool / "memory")
    scope_policy_path = _make_scope_policy(tmp_path)

    result = agent.execute(
        "example.com",
        {
            "fixture_data": fixture_payload,
            "scope_policy_path": str(scope_policy_path),
            "snl_interface": "tun0",
        },
    )

    assert result.status == "success"
    assert result.target_context.get("mode") == "stub_fixture"
    assert result.target_context.get("snl_interface") == "tun0"
    assert isinstance(result.target_context.get("telemetry"), list)
