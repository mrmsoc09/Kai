from __future__ import annotations
from ..base_tool_agent import BaseToolAgent
from typing import Any


class DNSValidatorAgent(BaseToolAgent):
    TOOL_NAME = "dnsvalidator"
    DEFAULT_TIMEOUT_SECONDS = 600

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        return ["dnsvalidator", target]
