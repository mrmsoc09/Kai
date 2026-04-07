from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List

from apps.backend.src.core.praison_topology import PraisonTopology, resolve_execution_order
from apps.backend.src.core.praison_node_executors import build_standard_node_callables

class ExecutionBenchmarkHarness:
    """
    K1 Execution Benchmark Harness.
    Compares different execution paths and measures latency/reliability.
    """

    def __init__(self):
        self.results: List[Dict[str, Any]] = []

    async def run_benchmark(self, scenario_name: str, state: Dict[str, Any]):
        """Runs a benchmark for a given scenario and state."""
        print(f"Starting benchmark: {scenario_name}")
        
        # 1. Resolve Topology
        topology = PraisonTopology.build_standard_bug_bounty(
            workflow_id="bench-workflow",
            program_id="bench-program",
            agent_specs={
                "GovernanceDirector": {"node_id": "GovernanceDirector"},
                "MissionDirector": {"node_id": "MissionDirector"},
                "PhaseCoordinator": {"node_id": "PhaseCoordinator"},
                "SurfaceMapper": {"node_id": "SurfaceMapper"},
                "ReconSpecialist": {"node_id": "ReconSpecialist"},
                "EvidenceAnalyst": {"node_id": "EvidenceAnalyst"},
                "ReportSynthesisAgent": {"node_id": "ReportSynthesisAgent"},
                "HandoffLiaison": {"node_id": "HandoffLiaison"},
            }
        )
        
        order = resolve_execution_order(topology)
        callables = build_standard_node_callables()
        
        start_mission = time.perf_counter()
        current_state = state.copy()
        
        stage_latencies = {}
        
        for node_id in order:
            if node_id not in callables:
                continue
                
            executor = callables[node_id]
            
            node_start = time.perf_counter()
            # Simulate state update
            update = executor(current_state)
            node_end = time.perf_counter()
            
            latency = (node_end - node_start) * 1000
            stage_latencies[node_id] = round(latency, 2)
            
            # Merge state
            current_state.update(update)
            
        end_mission = time.perf_counter()
        total_duration = (end_mission - start_mission) * 1000
        
        benchmark_result = {
            "scenario": scenario_name,
            "total_duration_ms": round(total_duration, 2),
            "stage_latencies": stage_latencies,
            "status": "success" if "error" not in current_state else "failed"
        }
        
        self.results.append(benchmark_result)
        return benchmark_result

    def generate_summary(self):
        """Generates a structured comparison summary."""
        return json.dumps(self.results, indent=2)

if __name__ == "__main__":
    harness = ExecutionBenchmarkHarness()
    
    # Simple Task scenario
    asyncio.run(harness.run_benchmark("simple_task", {"execution_mode": "graph_only"}))
    
    # Multi-stage Mission scenario
    asyncio.run(harness.run_benchmark("multi_stage_mission", {"execution_mode": "graph_only", "phase": "recon"}))
    
    print(harness.generate_summary())
