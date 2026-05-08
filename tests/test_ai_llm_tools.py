import pytest
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

# Assuming these wrappers are available in the tools_wrappers directory
# and can be imported directly for testing purposes.
# In a real setup, you might need to adjust sys.path or use a different import mechanism.
from tools_wrappers.garak_wrapper import GarakWrapper
from tools_wrappers.promptmap_wrapper import PromptMapWrapper
from tools_wrappers.llmguard_wrapper import LLMGuardWrapper
from tools_wrappers.pyrit_wrapper import PyRITWrapper

# Mock the KaiEngine's _run_docker_tool method for all wrappers
@pytest.fixture(autouse=True)
def mock_run_docker_tool(mocker):
    mocker.patch('kai_master.KaiEngine._run_docker_tool')
    # We'll directly simulate file writing for wrapper tests

# Mock the scope_enforcer for all tests
@pytest.fixture(autouse=True)
def mock_scope_enforcer(mocker):
    # By default, let everything be in scope for testing purposes
    mocker.patch('kai_master.KaiEngine.enforce_scope', return_value=True)

@pytest.fixture
def mock_base_output_dir(tmp_path):
    # Provide a temporary directory for output files
    return tmp_path

@pytest.fixture
def mock_run_id():
    return "test_run_llm_tools"

@pytest.fixture
def mock_target_llm_endpoint():
    return "http://mock-llm.ai/api"

# --- Garak Wrapper Tests ---
def test_garak_wrapper_run(mock_base_output_dir, mock_run_id, mock_target_llm_endpoint, mocker):
    # Mock the simulated _run_docker_tool_simulated in the wrapper itself
    mocker.patch.object(GarakWrapper, '_run_docker_tool_simulated', return_value=MagicMock(returncode=0))

    # Simulate Garak output directly into the mocked output directory
    garak_raw_output_path = mock_base_output_dir / "raw" / "garak" / "garak_raw.jsonl"
    garak_raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    simulated_results = [
        {"probe": "test", "vulnerability_type": "Prompt Injection", "severity": "High", "description": "Desc", "model": mock_target_llm_endpoint},
        {"probe": "test", "vulnerability_type": "Hallucination", "severity": "Low", "description": "Desc", "model": "http://outofscope.ai/api"}
    ]
    with open(garak_raw_output_path, "w") as f:
        for item in simulated_results:
            f.write(json.dumps(item) + "
")

    wrapper = GarakWrapper(
        run_id=mock_run_id,
        base_output_dir=mock_base_output_dir,
        target_llm_endpoint=mock_target_llm_endpoint,
        scope_enforcer=lambda x: x == mock_target_llm_endpoint # Specific scope enforcer for this test
    )
    findings = wrapper.run()

    assert len(findings) == 1 # Only one finding should be in scope
    assert findings[0]["vulnerability_type"] == "Prompt Injection"
    assert Path(mock_base_output_dir / "normalized" / f"garak_findings_{mock_run_id}.json").exists()

# --- PromptMap Wrapper Tests ---
def test_promptmap_wrapper_run(mock_base_output_dir, mock_run_id, mock_target_llm_endpoint, mocker):
    mocker.patch.object(PromptMapWrapper, '_run_docker_tool_simulated', return_value=MagicMock(returncode=0))

    promptmap_raw_output_path = mock_base_output_dir / "raw" / "promptmap" / "promptmap_raw.json"
    promptmap_raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    simulated_results = [
        {"test_case": "sql_injection", "vulnerable": True, "severity": "High", "description": "Desc"},
        {"test_case": "xss", "vulnerable": False, "severity": "Low", "description": "Desc"}
    ]
    with open(promptmap_raw_output_path, "w") as f:
        json.dump(simulated_results, f, indent=4)

    wrapper = PromptMapWrapper(
        run_id=mock_run_id,
        base_output_dir=mock_base_output_dir,
        target_llm_endpoint=mock_target_llm_endpoint,
        scope_enforcer=lambda x: True
    )
    findings = wrapper.run()

    assert len(findings) == 1
    assert findings[0]["test_case"] == "sql_injection"
    assert Path(mock_base_output_dir / "normalized" / f"promptmap_findings_{mock_run_id}.json").exists()

# --- LLMGuard Wrapper Tests ---
def test_llmguard_wrapper_run(mock_base_output_dir, mock_run_id, mock_target_llm_endpoint, mocker):
    mocker.patch.object(LLMGuardWrapper, '_run_docker_tool_simulated', return_value=MagicMock(returncode=0))

    llmguard_raw_output_path = mock_base_output_dir / "raw" / "llmguard" / "llmguard_raw.json"
    llmguard_raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    simulated_results = [
        {"policy_violation": "Sensitive Info", "alert_level": "CRITICAL", "prompt_text": "P1", "response_text": "R1"},
        {"policy_violation": "Jailbreak", "alert_level": "NONE", "prompt_text": "P2", "response_text": "R2"}
    ]
    with open(llmguard_raw_output_path, "w") as f:
        json.dump(simulated_results, f, indent=4)

    wrapper = LLMGuardWrapper(
        run_id=mock_run_id,
        base_output_dir=mock_base_output_dir,
        target_llm_endpoint=mock_target_llm_endpoint,
        scope_enforcer=lambda x: True
    )
    findings = wrapper.run()

    assert len(findings) == 1
    assert findings[0]["policy_violation"] == "Sensitive Information Leakage" # Wrapper should normalize type
    assert Path(mock_base_output_dir / "normalized" / f"llmguard_findings_{mock_run_id}.json").exists()

# --- PyRIT Wrapper Tests ---
def test_pyrit_wrapper_run(mock_base_output_dir, mock_run_id, mock_target_llm_endpoint, mocker):
    mocker.patch.object(PyRITWrapper, '_run_docker_tool_simulated', return_value=MagicMock(returncode=0))

    pyrit_raw_output_path = mock_base_output_dir / "raw" / "pyrit" / "pyrit_raw.json"
    pyrit_raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    simulated_results = [
        {"attack_strategy": "jailbreak", "vulnerability_found": True, "severity": "Critical", "description": "Desc"},
        {"attack_strategy": "no_vuln", "vulnerability_found": False, "severity": "Info", "description": "Desc"}
    ]
    with open(pyrit_raw_output_path, "w") as f:
        json.dump(simulated_results, f, indent=4)

    wrapper = PyRITWrapper(
        run_id=mock_run_id,
        base_output_dir=mock_base_output_dir,
        target_llm_endpoint=mock_target_llm_endpoint,
        scope_enforcer=lambda x: True
    )
    findings = wrapper.run()

    assert len(findings) == 1
    assert findings[0]["attack_strategy"] == "jailbreak"
    assert Path(mock_base_output_dir / "normalized" / f"pyrit_findings_{mock_run_id}.json").exists()
