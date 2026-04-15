from __future__ import annotations

from typing import Any, Dict, List, Optional
from ..base_tool_agent import BaseToolAgent
from ...core.vault_auth import VaultCredentialProvider
from ...core.protocol import KaisonFinding, KaisonResult, FindingType, Severity
from ...core.praison_execution_events import MissionEvent, get_event_bus

class BaseSecurityToolAgent(BaseToolAgent):
    """
    Standardized wrapper for security tools, integrated with Vault authentication.
    """

    def __init__(self, tool_id: str, memory_root: str | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self.tool_id = tool_id
        self.vault = VaultCredentialProvider()

    def get_secret(self, path: str, key: str) -> Optional[str]:
        return self.vault.get_secret(path, key)

    def emit_vrad_event(self, event_type: str, detail: Dict[str, Any]):
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type=event_type,
                    phase="tool_execution",
                    detail=detail
                )
            )
        except Exception:
            pass

class NucleiAgent(BaseSecurityToolAgent):
    TOOL_NAME = "nuclei"

    def build_command(self, target: str, options: Dict[str, Any] | None = None) -> List[str]:
        return ["nuclei", "-u", target, "-json"]

    def map_output(self, **kwargs) -> KaisonResult:
        # Implementation for parsing nuclei JSON output
        pass

class GowitnessAgent(BaseSecurityToolAgent):
    TOOL_NAME = "gowitness"

    def build_command(self, target: str, options: Dict[str, Any] | None = None) -> List[str]:
        return ["gowitness", "scan", "--url", target]

    def map_output(self, **kwargs) -> KaisonResult:
        self.emit_vrad_event("SCREENSHOT_COLLECTED", {"target": kwargs["target"]})
        pass
