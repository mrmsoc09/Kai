import pytest
from pathlib import Path
from apps.backend.src.agents.tools.ssrfmap.agent import SsrfmapAgent
from apps.backend.src.agents.tools.corsy.agent import CorsyAgent
from apps.backend.src.agents.tools.crlfuzz.agent import CrlfuzzAgent
from apps.backend.src.agents.tools.jwt_tool.agent import JwtToolAgent
from apps.backend.src.agents.tools.kiterunner.agent import KiterunnerAgent
from apps.backend.src.agents.tools.base_tool_agent import BaseToolAgent
from apps.backend.src.agents.tools import AGENT_REGISTRY

@pytest.mark.parametrize("agent_class, tool_name", [
    (SsrfmapAgent, "ssrfmap"),
    (CorsyAgent, "corsy"),
    (CrlfuzzAgent, "crlfuzz"),
    (JwtToolAgent, "jwt_tool"),
    (KiterunnerAgent, "kiterunner"),
])
def test_agent_inheritance_and_name(agent_class, tool_name):
    agent = agent_class()
    assert isinstance(agent, BaseToolAgent)
    assert agent.TOOL_NAME == tool_name

def test_registry_contains_all_15_tools():
    assert len(AGENT_REGISTRY) == 15
    for tool in ["subfinder", "amass", "dnsx", "gau", "waybackurls",
                 "httpx_probe", "naabu", "nuclei_scan", "dalfox", "sqlmap",
                 "ssrfmap", "corsy", "crlfuzz", "jwt_tool", "kiterunner"]:
        assert tool in AGENT_REGISTRY

def test_ssrfmap_command_building():
    agent = SsrfmapAgent()
    cmd = agent.build_command("http://example.com/api?url=FUZZ")
    assert "ssrfmap" in cmd
    assert "read" in cmd
    assert "-l" in cmd
    assert "aws,gcp,azure" in cmd

def test_corsy_command_building():
    agent = CorsyAgent()
    cmd = agent.build_command("http://example.com")
    assert "corsy" in cmd
    assert "-u" in cmd

def test_crlfuzz_command_building():
    agent = CrlfuzzAgent()
    cmd = agent.build_command("http://example.com")
    assert "crlfuzz" in cmd
    assert "-u" in cmd
    assert "-silent" in cmd

def test_jwt_tool_command_building():
    agent = JwtToolAgent()
    cmd = agent.build_command("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", {"attack_mode": True})
    assert "jwt_tool" in cmd
    assert "-M" in cmd
    assert "at" in cmd

def test_kiterunner_command_building():
    agent = KiterunnerAgent()
    cmd = agent.build_command("http://example.com/api")
    assert "kr" in cmd
    assert "scan" in cmd
    assert "-w" in cmd

def test_kiterunner_output_parsing():
    agent = KiterunnerAgent()
    raw = "[GET] [200] [1234] http://example.com/api/v1/users\n[POST] [403] [567] http://example.com/api/v1/admin\n"
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 2
    assert findings[0]["status_code"] == "200"
    assert findings[1]["method"] == "POST"
    
    signal, noise = agent.filter_noise(findings)
    assert len(signal) == 2
