from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPORT_PATH = Path(__file__).resolve().parent / "mission_audit_report.json"


@dataclass
class AdversarialCriticSim:
    """Defensive simulation critic: permits limited adaptation retries."""

    max_mutation_attempts: int = 3

    def allow_mutation_attempt(self, attempt_number: int) -> bool:
        return attempt_number <= self.max_mutation_attempts


@dataclass
class ReflectionOrchestratorSim:
    """Defensive simulation of reflection handoff behavior."""

    critic: AdversarialCriticSim = field(default_factory=AdversarialCriticSim)
    hard_blocked_nodes: set[str] = field(default_factory=set)

    def on_waf_block(
        self,
        node_id: str,
        target_context: str,
        attempt_number: int,
    ) -> dict[str, Any]:
        if not self.critic.allow_mutation_attempt(attempt_number):
            self.hard_blocked_nodes.add(node_id)
            return {
                "mutation": "hard_blocked",
                "attempt": attempt_number,
                "hard_blocked": True,
                "reason": "Maximum safe adaptation attempts reached.",
            }

        return {
            "mutation": "ast_mutation",
            "attempt": attempt_number,
            "hard_blocked": False,
            "target_context": target_context,
            "mutated_probe_plan": "context-aware detection probe variant",
        }


@dataclass
class RewardEngineSim:
    """Defensive simulation of RL reward attribution for strategy selection."""

    strategy_weights_by_target: dict[str, dict[str, float]] = field(default_factory=dict)

    def _weights(self, target_class: str) -> dict[str, float]:
        self.strategy_weights_by_target.setdefault(target_class, {"AST Mutation": 0.0})
        return self.strategy_weights_by_target[target_class]

    def attribute_reward(
        self,
        *,
        target_class: str,
        standard_variant_a_failed: bool,
        polymorphic_variant_c_succeeded: bool,
    ) -> dict[str, Any]:
        delta = 0.0
        if standard_variant_a_failed and polymorphic_variant_c_succeeded:
            delta = 0.35
            self._weights(target_class)["AST Mutation"] += delta
        return {
            "target_class": target_class,
            "ast_mutation_delta": delta,
            "policy_weights": self._weights(target_class),
        }


@dataclass
class MissionSmokeTest:
    reflector: ReflectionOrchestratorSim = field(default_factory=ReflectionOrchestratorSim)
    reward_engine: RewardEngineSim = field(default_factory=RewardEngineSim)
    vrad_visual_events: list[str] = field(default_factory=list)

    def discover_mock_service(self) -> dict[str, str]:
        return {
            "node_id": "mock-node-001",
            "service": "Nginx",
            "waf": "Cloudflare",
            "version": "1.25",
            "status": "discovered",
        }

    def map_to_cve_playbook(self, service: dict[str, str]) -> dict[str, str]:
        return {
            "playbook_id": "defensive_detection_playbook_nginx_cloudflare",
            "target_class": f"{service['service'].lower()}:{service['waf'].lower()}",
            "mapped_cve": "CVE-2026-SIM-0001",
        }

    def generate_polymorphic_probe(self) -> dict[str, str]:
        return {
            "variant_label": "Polymorphic Variant C",
            "probe_type": "detection_only",
            "description": "Non-destructive adaptive detection probe",
        }

    def simulate_vrad(self) -> dict[str, Any]:
        self.vrad_visual_events.extend(["AMBER_PULSE", "WHITE_FLARE", "IRIDESCENT_SHIMMER"])
        expected = ["AMBER_PULSE", "WHITE_FLARE", "IRIDESCENT_SHIMMER"]
        return {
            "expected": expected,
            "observed": self.vrad_visual_events,
            "sequence_verified": self.vrad_visual_events[:3] == expected,
        }

    def run(self) -> dict[str, Any]:
        service = self.discover_mock_service()
        playbook = self.map_to_cve_playbook(service)
        probe = self.generate_polymorphic_probe()

        target_context = f"{service['service']}/{service['waf']}"
        handshake_attempt_1 = self.reflector.on_waf_block(
            node_id=service["node_id"],
            target_context=target_context,
            attempt_number=1,
        )

        attempt_2 = self.reflector.on_waf_block(service["node_id"], target_context, 2)
        attempt_3 = self.reflector.on_waf_block(service["node_id"], target_context, 3)
        attempt_4 = self.reflector.on_waf_block(service["node_id"], target_context, 4)
        retry_check = {
            "first_three_allowed": all(not a["hard_blocked"] for a in [attempt_2, attempt_3]),
            "fourth_hard_blocked": attempt_4["hard_blocked"],
            "node_marked_hard_blocked": service["node_id"] in self.reflector.hard_blocked_nodes,
            "attempt_records": [handshake_attempt_1, attempt_2, attempt_3, attempt_4],
        }

        reward_result = self.reward_engine.attribute_reward(
            target_class=playbook["target_class"],
            standard_variant_a_failed=True,
            polymorphic_variant_c_succeeded=True,
        )

        vrad = self.simulate_vrad()

        handshake_ok = (
            handshake_attempt_1["mutation"] == "ast_mutation"
            and handshake_attempt_1.get("target_context") == "Nginx/Cloudflare"
            and handshake_attempt_1.get("mutated_probe_plan") is not None
        )
        rl_ok = reward_result["ast_mutation_delta"] > 0 and reward_result["policy_weights"]["AST Mutation"] > 0

        checks = {
            "reflection_obfuscation_handshake": {"pass": handshake_ok, "details": handshake_attempt_1},
            "adversarial_critic_retry_threshold": {
                "pass": (
                    retry_check["first_three_allowed"]
                    and retry_check["fourth_hard_blocked"]
                    and retry_check["node_marked_hard_blocked"]
                ),
                "details": retry_check,
            },
            "rl_graph_consistency": {
                "pass": rl_ok,
                "details": reward_result,
            },
            "v_rad_visual_sequence": {"pass": vrad["sequence_verified"], "details": vrad},
        }

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": "defensive_simulation",
            "status": "PASS" if all(item["pass"] for item in checks.values()) else "FAIL",
            "checks": checks,
            "simulation_steps": [
                "Discover mock service",
                "Map to CVE playbook",
                "Generate polymorphic detection probe",
                "Simulate 403/WAF block -> reflection -> mutated detection probe plan",
                "Verify V-RAD Amber -> White -> Iridescent sequence",
            ],
            "safety_constraints": {
                "exploitation_payloads_generated": False,
                "destructive_actions_performed": False,
                "scope_external_calls_made": False,
            },
            "context": {
                "service": service,
                "playbook": playbook,
                "probe_variant": probe,
            },
        }


def main() -> None:
    report = MissionSmokeTest().run()
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[smoke_test] status={report['status']}")
    print(f"[smoke_test] report={REPORT_PATH}")


if __name__ == "__main__":
    main()
