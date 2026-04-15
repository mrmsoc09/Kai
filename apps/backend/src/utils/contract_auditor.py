from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ContractAuditor:
    """
    Audits CVE Playbooks for Input/Output contract compliance.
    Implements a Generic Bridge for mapping tool outputs to playbook requirements.
    """

    def audit_playbook(self, playbook_data: Dict[str, Any]) -> List[str]:
        """Verify steps and tool contracts."""
        missing = []
        steps = playbook_data.get("playbook", {}).get("steps", [])
        for step in steps:
            # Audit tool usage inputs
            usage = step.get("tool_usage", {})
            if "parameters" not in usage:
                missing.append(f"Step {step.get('step_id')}: missing parameters contract")
        return missing

    def bridge_contracts(self, tool_output: Dict[str, Any], playbook_requirements: List[str]) -> Dict[str, Any]:
        """Maps tool output data to playbook variables."""
        bridge = {}
        for req in playbook_requirements:
            if req in tool_output:
                bridge[req] = tool_output[req]
            elif "metadata" in tool_output and req in tool_output["metadata"]:
                bridge[req] = tool_output["metadata"][req]
        return bridge
