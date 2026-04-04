import pytest
from pathlib import Path
from apps.backend.src.agents.tools.httpx_probe.agent import HttpxProbeAgent
from apps.backend.src.agents.tools.naabu.agent import NaabuAgent
from apps.backend.src.agents.tools.nuclei_scan.agent import NucleiScanAgent
from apps.backend.src.agents.tools.dalfox.agent import DalfoxAgent
from apps.backend.src.agents.tools.sqlmap.agent import SqlmapAgent
from apps.backend.src.agents.tools.base_tool_agent import BaseToolAgent

@pytest.mark.parametrize("agent_class, tool_name", [
    (HttpxProbeAgent, "httpx_probe"),
    (NaabuAgent, "naabu"),
    (NucleiScanAgent, "nuclei_scan"),
    (DalfoxAgent, "dalfox"),
    (SqlmapAgent, "sqlmap"),
])
def test_agent_inheritance_and_name(agent_class, tool_name):
    agent = agent_class()
    assert isinstance(agent, BaseToolAgent)
    assert agent.TOOL_NAME == tool_name

def test_httpx_probe_command_building():
    agent = HttpxProbeAgent()
    cmd = agent.build_command("example.com", {"input_file": "targets.txt"})
    assert "httpx" in cmd
    assert "-td" in cmd
    assert "-cdn" in cmd
    assert "-mc" in cmd
    assert "200,401,403,500" in cmd

def test_naabu_command_building():
    agent = NaabuAgent()
    cmd = agent.build_command("example.com")
    assert "naabu" in cmd
    assert "-p" in cmd
    assert agent.BBP_WEB_PORTS in cmd
    assert "-exclude-cdn" in cmd

def test_nuclei_scan_command_building():
    agent = NucleiScanAgent()
    # Test smart selection with spring
    cmd = agent.build_command("example.com", {"tech_list": ["Spring Boot"]})
    assert "nuclei" in cmd
    assert "tags/spring" in str(cmd)
    assert "-s" in cmd
    assert "critical,high,medium" in cmd

def test_dalfox_command_building():
    agent = DalfoxAgent()
    cmd = agent.build_command("http://example.com")
    assert "dalfox" in cmd
    assert "url" in cmd
    assert "--skip-bav" in cmd

def test_sqlmap_command_building():
    agent = SqlmapAgent()
    cmd = agent.build_command("http://example.com/id=1")
    assert "sqlmap" in cmd
    assert "--level" in cmd
    assert "2" in cmd
    assert "--risk" in cmd
    assert "1" in cmd
    assert "--technique" in cmd
    assert "B" in cmd
    assert "--batch" in cmd

def test_knowledge_file_presence():
    tools = ["httpx_probe", "naabu", "nuclei_scan", "dalfox", "sqlmap"]
    required_files = [
        "tool_overview.md",
        "advanced_techniques.md",
        "output_patterns.md",
        "false_positives.md",
        "use_cases.md"
    ]
    base_path = Path("apps/backend/src/agents/tools")
    for tool in tools:
        knowledge_dir = base_path / tool / "knowledge"
        assert knowledge_dir.exists()
        for f in required_files:
            assert (knowledge_dir / f).exists()

def test_httpx_output_parsing():
    agent = HttpxProbeAgent()
    raw = '{"url": "https://test.example.com", "status_code": 403, "server": "cloudflare"}'
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 1
    f = findings[0]
    # Support both old schema (top-level status_code) and new standardized schema (context dict)
    status = f.get("status_code") or f.get("context", {}).get("status_code", 0)
    assert status == 403, f"Expected status_code 403, got: {f}"

    signal, noise = agent.filter_noise(findings)
    assert len(signal) == 1
    assert signal[0].get("signal_reason") in ("waf_403", "app_403", "auth_required")

def test_naabu_output_parsing():
    agent = NaabuAgent()
    raw = "example.com:9200\nexample.com:80\n"
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 2
    f = findings[0]
    # Support both old schema (service key) and new standardized schema (context dict)
    service = (
        f.get("service")
        or f.get("context", {}).get("service", "")
        or f.get("context", {}).get("service_hint", "")
    )
    assert "elasticsearch" in service.lower(), f"Expected elasticsearch service, got: {f}"


# ---------------------------------------------------------------------------
# Knowledge file content tests — all 10 batch2 tools
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool,filename,min_chars", [
    ("httpx_probe", "tool_overview.md", 150),
    ("httpx_probe", "advanced_techniques.md", 200),
    ("httpx_probe", "output_patterns.md", 150),
    ("httpx_probe", "false_positives.md", 100),
    ("httpx_probe", "use_cases.md", 150),
    ("naabu", "tool_overview.md", 100),
    ("naabu", "advanced_techniques.md", 200),
    ("naabu", "output_patterns.md", 100),
    ("naabu", "false_positives.md", 80),
    ("naabu", "use_cases.md", 100),
    ("nuclei_scan", "tool_overview.md", 150),
    ("nuclei_scan", "advanced_techniques.md", 300),
    ("nuclei_scan", "output_patterns.md", 150),
    ("nuclei_scan", "false_positives.md", 150),
    ("nuclei_scan", "use_cases.md", 200),
    ("dalfox", "tool_overview.md", 100),
    ("dalfox", "advanced_techniques.md", 150),
    ("dalfox", "output_patterns.md", 100),
    ("dalfox", "false_positives.md", 100),
    ("dalfox", "use_cases.md", 150),
    ("sqlmap", "tool_overview.md", 150),
    ("sqlmap", "advanced_techniques.md", 200),
    ("sqlmap", "output_patterns.md", 100),
    ("sqlmap", "false_positives.md", 100),
    ("sqlmap", "use_cases.md", 150),
    ("ssrfmap", "tool_overview.md", 100),
    ("ssrfmap", "advanced_techniques.md", 200),
    ("ssrfmap", "output_patterns.md", 150),
    ("ssrfmap", "false_positives.md", 150),
    ("ssrfmap", "use_cases.md", 300),
    ("corsy", "tool_overview.md", 100),
    ("corsy", "advanced_techniques.md", 200),
    ("corsy", "output_patterns.md", 200),
    ("corsy", "false_positives.md", 150),
    ("corsy", "use_cases.md", 300),
    ("crlfuzz", "tool_overview.md", 150),
    ("crlfuzz", "advanced_techniques.md", 200),
    ("crlfuzz", "output_patterns.md", 150),
    ("crlfuzz", "false_positives.md", 150),
    ("crlfuzz", "use_cases.md", 300),
    ("jwt_tool", "tool_overview.md", 150),
    ("jwt_tool", "advanced_techniques.md", 300),
    ("jwt_tool", "output_patterns.md", 150),
    ("jwt_tool", "false_positives.md", 150),
    ("jwt_tool", "use_cases.md", 300),
    ("kiterunner", "tool_overview.md", 100),
    ("kiterunner", "advanced_techniques.md", 300),
    ("kiterunner", "output_patterns.md", 150),
    ("kiterunner", "false_positives.md", 150),
    ("kiterunner", "use_cases.md", 300),
])
def test_knowledge_file_content_length(tool, filename, min_chars):
    path = Path(f"apps/backend/src/agents/tools/{tool}/knowledge/{filename}")
    assert path.exists(), f"{tool}/{filename} missing"
    content = path.read_text()
    assert len(content) >= min_chars, (
        f"{tool}/{filename} too short: {len(content)} < {min_chars}"
    )


# ---------------------------------------------------------------------------
# Additional tool coverage — agents not in original parametrize
# ---------------------------------------------------------------------------

from apps.backend.src.agents.tools.ssrfmap.agent import SsrfmapAgent
from apps.backend.src.agents.tools.corsy.agent import CorsyAgent
from apps.backend.src.agents.tools.crlfuzz.agent import CrlfuzzAgent
from apps.backend.src.agents.tools.jwt_tool.agent import JwtToolAgent
from apps.backend.src.agents.tools.kiterunner.agent import KiterunnerAgent

@pytest.mark.parametrize("agent_class, tool_name", [
    (SsrfmapAgent, "ssrfmap"),
    (CorsyAgent, "corsy"),
    (CrlfuzzAgent, "crlfuzz"),
    (JwtToolAgent, "jwt_tool"),
    (KiterunnerAgent, "kiterunner"),
])
def test_remaining_agents_inherit_base(agent_class, tool_name):
    agent = agent_class()
    assert isinstance(agent, BaseToolAgent)
    assert agent.TOOL_NAME == tool_name


@pytest.mark.parametrize("agent_class, tool_name", [
    (SsrfmapAgent, "ssrfmap"),
    (CorsyAgent, "corsy"),
    (CrlfuzzAgent, "crlfuzz"),
    (JwtToolAgent, "jwt_tool"),
    (KiterunnerAgent, "kiterunner"),
])
def test_remaining_agents_build_command(agent_class, tool_name):
    agent = agent_class()
    cmd = agent.build_command("https://example.com")
    assert isinstance(cmd, list)
    assert len(cmd) >= 2
    assert all(isinstance(c, str) for c in cmd)


@pytest.mark.parametrize("agent_class, tool_name", [
    (SsrfmapAgent, "ssrfmap"),
    (CorsyAgent, "corsy"),
    (CrlfuzzAgent, "crlfuzz"),
    (JwtToolAgent, "jwt_tool"),
    (KiterunnerAgent, "kiterunner"),
])
def test_remaining_agents_parse_empty_output(agent_class, tool_name):
    agent = agent_class()
    findings = agent.parse_output("", "example.com")
    assert isinstance(findings, list)


@pytest.mark.parametrize("agent_class, tool_name", [
    (SsrfmapAgent, "ssrfmap"),
    (CorsyAgent, "corsy"),
    (CrlfuzzAgent, "crlfuzz"),
    (JwtToolAgent, "jwt_tool"),
    (KiterunnerAgent, "kiterunner"),
])
def test_remaining_agents_filter_noise_empty(agent_class, tool_name):
    agent = agent_class()
    signal, noise = agent.filter_noise([])
    assert isinstance(signal, list)
    assert isinstance(noise, list)


# ---------------------------------------------------------------------------
# Behaviour tests — safe-mode enforcement and critical flags
# ---------------------------------------------------------------------------

def test_sqlmap_no_dump_flag():
    agent = SqlmapAgent()
    cmd = agent.build_command("http://example.com/page?id=1")
    cmd_str = " ".join(cmd)
    assert "--dump" not in cmd_str, "sqlmap --dump must NEVER appear in automated mode"
    assert "--level" in cmd_str
    assert "--batch" in cmd_str


def test_sqlmap_technique_boolean_only():
    agent = SqlmapAgent()
    cmd = agent.build_command("http://example.com/page?id=1")
    cmd_str = " ".join(cmd)
    assert "--technique" in cmd_str
    assert "B" in cmd_str


def test_nuclei_severity_excludes_info():
    agent = NucleiScanAgent()
    cmd = agent.build_command("example.com")
    cmd_str = " ".join(cmd)
    # info severity should not appear in the severity filter
    severity_idx = cmd.index("-s") if "-s" in cmd else -1
    if severity_idx >= 0 and severity_idx + 1 < len(cmd):
        severity_val = cmd[severity_idx + 1]
        assert "info" not in severity_val, "nuclei should not scan for 'info' severity in automated mode"


def test_kiterunner_uses_kite_wordlist():
    agent = KiterunnerAgent()
    cmd = agent.build_command("https://api.example.com")
    cmd_str = " ".join(cmd)
    assert "kr" in cmd_str or "kiterunner" in cmd_str
    assert ".kite" in cmd_str, "kiterunner must use .kite wordlist format"


def test_jwt_tool_attack_mode_flag():
    agent = JwtToolAgent()
    cmd = agent.build_command("eyJhbGciOiJSUzI1NiJ9.test.sig", {"attack_mode": True})
    cmd_str = " ".join(cmd)
    assert "jwt_tool" in cmd_str
    assert "-M" in cmd_str or "-X" in cmd_str or "at" in cmd_str


def test_ssrfmap_targets_cloud_metadata():
    agent = SsrfmapAgent()
    assert hasattr(agent, "CLOUD_METADATA_TARGETS"), "ssrfmap agent must define CLOUD_METADATA_TARGETS"
    assert any("169.254.169.254" in t for t in agent.CLOUD_METADATA_TARGETS)


# ---------------------------------------------------------------------------
# Memory system — all 10 tools
# ---------------------------------------------------------------------------

def test_batch2_memory_dirs_exist():
    tools = ["httpx_probe", "naabu", "nuclei_scan", "dalfox", "sqlmap",
             "ssrfmap", "corsy", "crlfuzz", "jwt_tool", "kiterunner"]
    base = Path("apps/backend/src/agents/tools")
    for tool in tools:
        memory_dir = base / tool / "memory"
        assert memory_dir.exists(), f"{tool}/memory directory missing"


def test_batch2_knowledge_dirs_complete():
    tools = ["httpx_probe", "naabu", "nuclei_scan", "dalfox", "sqlmap",
             "ssrfmap", "corsy", "crlfuzz", "jwt_tool", "kiterunner"]
    required = ["tool_overview.md", "advanced_techniques.md",
                "output_patterns.md", "false_positives.md", "use_cases.md"]
    base = Path("apps/backend/src/agents/tools")
    for tool in tools:
        for f in required:
            p = base / tool / "knowledge" / f
            assert p.exists(), f"MISSING: {tool}/knowledge/{f}"
