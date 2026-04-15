from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueuedTask:
    stage: str
    tool_id: str
    urgency: int
    estimated_memory_gb: float


class GlobalTaskQueue:
    """
    Lightweight deterministic queue for scan task ordering under memory ceilings.

    This does not execute tasks itself. It provides:
    - urgency-based ordering
    - conservative concurrency suggestions from a global memory cap
    """

    # Approximate memory envelopes per tool family in GB.
    _TOOL_MEMORY_GB: dict[str, float] = {
        "nuclei_scan": 2.5,
        "reconftw": 3.0,
        "nmap": 1.4,
        "masscan": 1.0,
        "naabu": 0.8,
        "httpx_probe": 0.7,
        "sqlmap": 0.9,
        "dalfox": 0.6,
        "ffuf": 0.5,
        "katana": 0.7,
        "amass": 0.9,
        "subfinder": 0.4,
        "dnsx": 0.3,
    }

    _STAGE_URGENCY: dict[str, int] = {
        "exploitation": 95,
        "vulnerability": 90,
        "vulnerability_scan": 90,
        "analysis": 80,
        "reconnaissance": 70,
        "recon": 70,
        "enumeration": 65,
        "reporting": 50,
    }

    def __init__(self, *, max_memory_gb: float = 40.0) -> None:
        self.max_memory_gb = max(1.0, float(max_memory_gb))

    def order_stage_phases(self, *, stage: str, phases: list[Any]) -> list[Any]:
        """
        Return phases sorted by urgency descending, preserving stable order ties.
        """
        ranked = []
        for index, phase in enumerate(phases):
            dispatch = (
                phase.input_payload_json.get("dispatch")
                if isinstance(getattr(phase, "input_payload_json", None), dict)
                else {}
            )
            tool_id = str(dispatch.get("tool_id") or "").strip()
            ranked.append((self._urgency_for(stage, tool_id), index, phase))

        ranked.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        return [item[2] for item in ranked]

    def suggested_concurrency(self, *, tool_ids: list[str], requested: int) -> int:
        """
        Suggest safe concurrency under global memory cap.
        """
        requested = max(1, int(requested))
        if not tool_ids:
            return requested

        heaviest = max(self._TOOL_MEMORY_GB.get(tool_id, 0.6) for tool_id in tool_ids)
        if heaviest <= 0:
            return requested

        # Reserve half the node memory for DB, API plane, and OS cache.
        scan_budget = max(1.0, self.max_memory_gb * 0.5)
        capacity = max(1, int(scan_budget // heaviest))
        return max(1, min(requested, capacity))

    def _urgency_for(self, stage: str, tool_id: str) -> int:
        base = 60
        stage_l = stage.lower().strip()
        tool_l = tool_id.lower().strip()

        for key, val in self._STAGE_URGENCY.items():
            if key in stage_l:
                base = max(base, val)
        if "nuclei" in tool_l or "sqlmap" in tool_l or "dalfox" in tool_l:
            base = max(base, 92)
        if "httpx" in tool_l or "naabu" in tool_l or "nmap" in tool_l:
            base = max(base, 78)
        if "subfinder" in tool_l or "amass" in tool_l or "assetfinder" in tool_l:
            base = max(base, 70)
        return base

