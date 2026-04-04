from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HandoffReport:
    """Structured report passed to the next agent in the pipeline."""

    tool: str
    target: str
    scan_id: str
    signal_findings: list[dict[str, Any]] = field(default_factory=list)
    noise_findings: list[dict[str, Any]] = field(default_factory=list)
    next_agent_instructions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "target": self.target,
            "scan_id": self.scan_id,
            "signal_count": len(self.signal_findings),
            "noise_count": len(self.noise_findings),
            "signal_findings": self.signal_findings,
            "noise_findings": self.noise_findings,
            "next_agent_instructions": self.next_agent_instructions,
            "metadata": self.metadata,
        }

    @property
    def is_empty(self) -> bool:
        return len(self.signal_findings) == 0

    def top_findings(self, n: int = 10) -> list[dict[str, Any]]:
        return self.signal_findings[:n]
