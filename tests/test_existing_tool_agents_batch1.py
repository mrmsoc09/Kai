import pytest
from pathlib import Path
from apps.backend.src.agents.tools.subfinder.agent import SubfinderAgent
from apps.backend.src.agents.tools.amass.agent import AmassAgent
from apps.backend.src.agents.tools.dnsx.agent import DnsxAgent
from apps.backend.src.agents.tools.gau.agent import GauAgent
from apps.backend.src.agents.tools.waybackurls.agent import WaybackurlsAgent
from apps.backend.src.agents.tools.base_tool_agent import BaseToolAgent

@pytest.mark.parametrize("agent_class, tool_name", [
    (SubfinderAgent, "subfinder"),
    (AmassAgent, "amass"),
    (DnsxAgent, "dnsx"),
    (GauAgent, "gau"),
    (WaybackurlsAgent, "waybackurls"),
])
def test_agent_inheritance_and_name(agent_class, tool_name):
    agent = agent_class()
    assert isinstance(agent, BaseToolAgent)
    assert agent.TOOL_NAME == tool_name

def test_subfinder_command_building():
    agent = SubfinderAgent()
    cmd = agent.build_command("example.com", {"recursive": True})
    assert "subfinder" in cmd
    assert "-d" in cmd
    assert "example.com" in cmd
    assert "-all" in cmd  # Defaulted to True
    assert "-recursive" in cmd

def test_amass_command_building():
    agent = AmassAgent()
    # Test standard enum
    cmd = agent.build_command("example.com")
    assert "amass" in cmd
    assert "enum" in cmd
    assert "-passive" in cmd
    
    # Test intel mode
    cmd_intel = agent.build_command("example.com", {"intel": True})
    assert "amass" in cmd_intel
    assert "intel" in cmd_intel
    assert "-whois" in cmd_intel

def test_dnsx_command_building():
    agent = DnsxAgent()
    cmd = agent.build_command("example.com")
    assert "dnsx" in cmd
    assert "-cname" in cmd
    assert "-wd" in cmd
    assert "example.com" in cmd

def test_gau_command_building():
    agent = GauAgent()
    cmd = agent.build_command("example.com")
    assert "gau" in cmd
    assert "--timeout" in cmd
    assert "900" in cmd

def test_waybackurls_command_building():
    agent = WaybackurlsAgent()
    cmd = agent.build_command("example.com")
    assert "waybackurls" in cmd[2]
    assert "-dates" in cmd[2]

def test_knowledge_file_presence():
    tools = ["subfinder", "amass", "dnsx", "gau", "waybackurls"]
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

def test_subfinder_output_parsing():
    agent = SubfinderAgent()
    raw = "www.example.com\napi.example.com\n"
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 2
    assert findings[0]["subdomain"] == "www.example.com"

def test_dnsx_output_parsing():
    agent = DnsxAgent()
    # Test plaintext parsing
    raw = "test.example.com [1.2.3.4]\n"
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 1
    assert findings[0]["subdomain"] == "test.example.com"
    assert "1.2.3.4" in findings[0]["a_records"]


# ---------------------------------------------------------------------------
# Knowledge file content tests (min-length assertions)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool,filename,min_chars", [
    ("subfinder", "tool_overview.md", 200),
    ("subfinder", "advanced_techniques.md", 300),
    ("subfinder", "output_patterns.md", 200),
    ("subfinder", "false_positives.md", 150),
    ("subfinder", "use_cases.md", 400),
    ("amass", "tool_overview.md", 200),
    ("amass", "advanced_techniques.md", 200),
    ("amass", "output_patterns.md", 100),
    ("amass", "false_positives.md", 100),
    ("amass", "use_cases.md", 200),
    ("dnsx", "tool_overview.md", 150),
    ("dnsx", "advanced_techniques.md", 200),
    ("dnsx", "output_patterns.md", 100),
    ("dnsx", "false_positives.md", 100),
    ("dnsx", "use_cases.md", 150),
    ("gau", "tool_overview.md", 150),
    ("gau", "advanced_techniques.md", 200),
    ("gau", "output_patterns.md", 150),
    ("gau", "false_positives.md", 100),
    ("gau", "use_cases.md", 200),
    ("waybackurls", "tool_overview.md", 100),
    ("waybackurls", "advanced_techniques.md", 150),
    ("waybackurls", "output_patterns.md", 100),
    ("waybackurls", "false_positives.md", 80),
    ("waybackurls", "use_cases.md", 150),
])
def test_knowledge_file_content_length(tool, filename, min_chars):
    path = Path(f"apps/backend/src/agents/tools/{tool}/knowledge/{filename}")
    assert path.exists(), f"{tool}/{filename} missing"
    content = path.read_text()
    assert len(content) >= min_chars, (
        f"{tool}/{filename} too short: {len(content)} < {min_chars}"
    )


# ---------------------------------------------------------------------------
# parse_output / filter_noise behaviour tests
# ---------------------------------------------------------------------------

def test_subfinder_filters_non_target_domains():
    agent = SubfinderAgent()
    raw = "api.example.com\nadmin.example.com\nevil.notexample.com\n"
    findings = agent.parse_output(raw, "example.com")
    values = [f["subdomain"] for f in findings]
    assert "api.example.com" in values
    assert "admin.example.com" in values
    assert "evil.notexample.com" not in values


def test_subfinder_high_signal_keywords_in_signal():
    agent = SubfinderAgent()
    findings = [
        {"subdomain": "admin.example.com", "value": "admin.example.com",
         "source": "subfinder", "target": "example.com"},
        {"subdomain": "mail.example.com", "value": "mail.example.com",
         "source": "subfinder", "target": "example.com"},
    ]
    signal, noise = agent.filter_noise(findings)
    signal_vals = [s["subdomain"] for s in signal]
    noise_vals = [n["subdomain"] for n in noise]
    assert "admin.example.com" in signal_vals
    assert "mail.example.com" in noise_vals


def test_gau_timeout_default_is_900():
    agent = GauAgent()
    cmd = agent.build_command("example.com")
    assert "900" in cmd, "GAU default timeout must be 900s (was 240s — caused 81% failure rate)"


def test_gau_parse_output_extracts_urls():
    agent = GauAgent()
    raw = "https://example.com/page?id=1&user=test\nhttps://example.com/image.jpg\n"
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) >= 1
    urls = [f["url"] for f in findings]
    assert any("id=1" in u for u in urls)


def test_amass_intel_mode_builds_correct_command():
    agent = AmassAgent()
    cmd = agent.build_command("example.com", {"intel": True})
    assert "intel" in cmd
    assert "amass" in cmd


def test_dnsx_cname_field_in_findings():
    agent = DnsxAgent()
    raw = "test.example.com [1.2.3.4]\n"
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 1
    assert "a_records" in findings[0] or "1.2.3.4" in str(findings[0])


def test_waybackurls_command_includes_dates_flag():
    agent = WaybackurlsAgent()
    cmd = agent.build_command("example.com")
    cmd_str = " ".join(cmd)
    assert "waybackurls" in cmd_str
    assert "-dates" in cmd_str


# ---------------------------------------------------------------------------
# Memory system tests
# ---------------------------------------------------------------------------

def test_memory_dirs_exist():
    tools = ["subfinder", "amass", "dnsx", "gau", "waybackurls"]
    base = Path("apps/backend/src/agents/tools")
    for tool in tools:
        memory_dir = base / tool / "memory"
        assert memory_dir.exists(), f"{tool}/memory directory missing"


def test_memory_jsonl_files_exist():
    tools = ["subfinder", "amass", "dnsx", "gau", "waybackurls"]
    base = Path("apps/backend/src/agents/tools")
    for tool in tools:
        for jsonl in ("scan_history.jsonl", "findings_correlation.jsonl"):
            p = base / tool / "memory" / jsonl
            assert p.exists(), f"{tool}/memory/{jsonl} missing"
