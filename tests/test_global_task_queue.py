from __future__ import annotations

from dataclasses import dataclass

from apps.backend.src.core.global_task_queue import GlobalTaskQueue


@dataclass
class _Phase:
    phase_order: int
    input_payload_json: dict


def test_global_task_queue_orders_vuln_tools_first() -> None:
    queue = GlobalTaskQueue(max_memory_gb=40)
    phases = [
        _Phase(phase_order=1, input_payload_json={"dispatch": {"tool_id": "subfinder"}}),
        _Phase(phase_order=2, input_payload_json={"dispatch": {"tool_id": "nuclei_scan"}}),
        _Phase(phase_order=3, input_payload_json={"dispatch": {"tool_id": "httpx_probe"}}),
    ]
    ordered = queue.order_stage_phases(stage="vulnerability_scan", phases=phases)
    ids = [p.input_payload_json["dispatch"]["tool_id"] for p in ordered]
    assert ids[0] == "nuclei_scan"


def test_global_task_queue_caps_concurrency_by_memory() -> None:
    queue = GlobalTaskQueue(max_memory_gb=4)
    # Nuclei is modeled as heavy; under 4GB cap, queue should avoid high fanout.
    suggested = queue.suggested_concurrency(
        tool_ids=["nuclei_scan", "httpx_probe"],
        requested=8,
    )
    assert suggested == 1

