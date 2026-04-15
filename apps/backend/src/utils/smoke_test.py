from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.backend.src.agents.reflection.reflection_orchestrator import ReflectionOrchestrator
from apps.backend.src.core.attack_surface_graph import AttackSurfaceGraph, EdgeType
from apps.backend.src.core.experience_engine import ExperienceEngine
from apps.backend.src.core.praison_execution_events import get_event_bus, reset_event_bus
from apps.backend.src.rl.optimization.reward_function import RewardEngine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mission_smoke_test")


class MissionSmokeTest:
    def __init__(self) -> None:
        reset_event_bus()
        self.event_bus = get_event_bus()
        self.graph = AttackSurfaceGraph()
        self.engine = ExperienceEngine.get_instance()
        self.reflector = ReflectionOrchestrator(graph=self.graph, max_mutation_attempts=3)
        self.reward_engine = RewardEngine()

    @staticmethod
    def _contains_subsequence(items: List[str], sequence: List[str]) -> bool:
        if not sequence:
            return True
        idx = 0
        for item in items:
            if item == sequence[idx]:
                idx += 1
                if idx == len(sequence):
                    return True
        return False

    def _discover_mock_service(self) -> Dict[str, Any]:
        self.graph.add_asset_node("target_node", "web", {"hostname": "mock.target"})
        self.graph.add_service_node(
            "svc_nginx",
            443,
            "tcp",
            {"service": "Nginx", "version": "1.25", "waf": "Cloudflare"},
        )
        self.graph.create_edge("target_node", "svc_nginx", EdgeType.HOSTS)
        return {
            "target_node": "target_node",
            "service": "Nginx",
            "version": "1.25",
            "waf": "Cloudflare",
        }

    def _map_to_cve_playbook(self, service_details: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "cve_id": "CVE-2026-90001",
            "playbook_id": "nginx_cloudflare_reflection_probe",
            "target_class": f"{service_details['service'].lower()}:{service_details['waf'].lower()}",
        }

    def _run_reflection_handshake(self, playbook_id: str) -> Dict[str, Any]:
        result = {
            "error": "403 Forbidden",
            "output": "Cloudflare WAF blocked request",
            "payload": "GET /?q=<svg/onload=1>",
            "payload_type": "python",
            "target_fingerprint": {"service": "Nginx", "waf": "Cloudflare", "version": "1.25"},
        }
        mutation = self.reflector.post_execution_reflection(playbook_id, result, "target_node")
        return mutation or {}

    def _validate_retry_threshold(self) -> Dict[str, Any]:
        playbook = "retry_threshold_probe"
        result = {
            "error": "403 Forbidden",
            "output": "Cloudflare WAF blocked request",
            "payload": "GET /?q=<probe>",
            "payload_type": "python",
            "target_fingerprint": {"service": "Nginx", "waf": "Cloudflare"},
        }
        attempts: List[Dict[str, Any]] = []
        for _ in range(4):
            attempts.append(self.reflector.post_execution_reflection(playbook, result, "target_node") or {})
        first_three_allowed = all(not x.get("hard_blocked", False) for x in attempts[:3])
        fourth_blocked = bool(attempts[3].get("hard_blocked", False))
        graph_node = self.graph._graph.nodes.get("target_node", {})
        hard_blocked_in_graph = (
            graph_node.get("block_state") == "HARD_BLOCKED"
            or bool((graph_node.get("metadata") or {}).get("hard_blocked"))
        )
        return {
            "first_three_allowed": first_three_allowed,
            "fourth_blocked": fourth_blocked,
            "hard_blocked_in_graph": hard_blocked_in_graph,
            "attempt_records": attempts,
        }

    def _validate_rl_graph_consistency(self, mapped: Dict[str, Any]) -> Dict[str, Any]:
        target_fp = {"service": "nginx", "waf": "cloudflare", "version": "1.25"}
        target_class = mapped["target_class"]

        self.engine.learn_from_outcome(
            target_fingerprint=target_fp,
            playbook_id=mapped["playbook_id"],
            mutation_used="standard_variant_a",
            outcome="WAF_Trigger",
            metadata={"variant_label": "Standard Variant A", "target_class": target_class},
        )
        attribution = self.reward_engine.attribute_reward(
            "Success",
            {
                "variant_label": "Polymorphic Variant C",
                "standard_variant_a_failed": True,
                "target_class": target_class,
            },
        )
        self.engine.learn_from_outcome(
            target_fingerprint=target_fp,
            playbook_id=mapped["playbook_id"],
            mutation_used="polymorphic_variant_c",
            outcome="Success",
            metadata={
                "variant_label": "Polymorphic Variant C",
                "strategy": attribution["strategy"],
                "target_class": target_class,
            },
        )
        weights = self.engine.get_strategy_weights(target_class)
        boosted = float(weights.get("AST Mutation", 0.0)) > 0.0
        return {
            "target_class": target_class,
            "reward_attribution": attribution,
            "policy_weights": weights,
            "ast_mutation_boosted": boosted,
        }

    def _validate_vrad_sequence(self) -> Dict[str, Any]:
        events = self.event_bus.recent(400)
        visuals = [str((e.detail or {}).get("v-rad_visual", "")) for e in events]
        expected = ["AMBER_PULSE", "WHITE_FLARE", "IRIDESCENT_SHIMMER"]
        return {
            "expected_sequence": expected,
            "observed_visuals": visuals,
            "sequence_verified": self._contains_subsequence(visuals, expected),
        }

    def run(self) -> Dict[str, Any]:
        service = self._discover_mock_service()
        mapped = self._map_to_cve_playbook(service)
        handshake = self._run_reflection_handshake(mapped["playbook_id"])
        retry_check = self._validate_retry_threshold()
        rl_check = self._validate_rl_graph_consistency(mapped)
        vrad_check = self._validate_vrad_sequence()

        handshake_ok = (
            handshake.get("mutation") == "ast_mutation"
            and handshake.get("target_context") == "Nginx/Cloudflare"
            and bool(handshake.get("mutated_payload"))
        )
        retry_ok = (
            retry_check["first_three_allowed"]
            and retry_check["fourth_blocked"]
            and retry_check["hard_blocked_in_graph"]
        )
        rl_ok = rl_check["ast_mutation_boosted"] and rl_check["reward_attribution"]["ast_mutation_delta"] > 0
        vrad_ok = vrad_check["sequence_verified"]

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "PASS" if all([handshake_ok, retry_ok, rl_ok, vrad_ok]) else "FAIL",
            "checks": {
                "reflection_obfuscation_handshake": {
                    "pass": handshake_ok,
                    "details": handshake,
                },
                "adversarial_critic_retry_threshold": {
                    "pass": retry_ok,
                    "details": retry_check,
                },
                "rl_graph_consistency": {
                    "pass": rl_ok,
                    "details": rl_check,
                },
                "smoke_loop_vrad_sequence": {
                    "pass": vrad_ok,
                    "details": vrad_check,
                },
            },
            "simulation_steps": [
                "Discover mock service",
                "Map to CVE playbook",
                "Generate polymorphic payload",
                "Simulate 403 -> Reflection -> Mutated payload",
                "Verify V-RAD Amber -> White -> Iridescent sequence",
            ],
        }
        return report


def write_report(report: Dict[str, Any]) -> Dict[str, str]:
    artifacts_path = REPO_ROOT / "artifacts" / "reports" / "mission_audit_report.json"
    root_path = REPO_ROOT / "mission_audit_report.json"
    artifacts_path.parent.mkdir(parents=True, exist_ok=True)
    artifacts_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    root_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"artifacts_report": str(artifacts_path), "root_report": str(root_path)}


if __name__ == "__main__":
    suite = MissionSmokeTest()
    result = suite.run()
    paths = write_report(result)
    logger.info("Mission smoke test completed: %s", result["status"])
    logger.info("Report written to %s and %s", paths["artifacts_report"], paths["root_report"])
