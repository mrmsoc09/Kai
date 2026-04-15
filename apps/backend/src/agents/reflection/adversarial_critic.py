from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ...core.experience_engine import ExperienceEngine
from ...core.praison_execution_events import MissionEvent, get_event_bus
from ...core.vault_auth import VaultCredentialProvider

logger = logging.getLogger(__name__)

class AdversarialCritic:
    """
    K1 Adversarial Reflection Loop Agent.
    Audits InstructionTuples and suggests payload mutations.
    """

    def __init__(self) -> None:
        self.memory = ExperienceEngine.get_instance()
        self.vault = VaultCredentialProvider()
        self.hard_block_threshold = 3

    def allow_mutation_attempt(self, attempt_number: int) -> bool:
        """
        Allow at least 3 mutation attempts before declaring a hard block.
        """
        return attempt_number <= self.hard_block_threshold

    def audit_instruction(self, instruction: Dict[str, Any], target: str) -> Dict[str, Any]:
        """
        Pre-Flight Audit: Evaluate instruction against Memory, WAF history, and Vault keys.
        """
        playbook_id = instruction.get("playbook", "generic")
        params = instruction.get("params", {})
        
        # 1. Ensure keys are loaded via Vault
        if "api_key_path" in params:
            key = self.vault.get_secret(params["api_key_path"], "key")
            if not key:
                return {"decision": "DENY", "reason": "Missing required API key in Vault"}
            params["api_key"] = key
        
        # 2. Query reflex engine for tactical strategy
        tactical = self.memory.recommend_tactical_action(
            target_fingerprint={"service": target}, 
            playbook_id=playbook_id
        )
        
        decision = "APPROVE"
        if tactical.get("score", 0.0) < -0.5:
            decision = "MUTATE"
            
        # 3. Emit Telemetry
        self._emit_vrad_pulse("REFLECTION_DECISION", {
            "decision": decision,
            "playbook": playbook_id,
            "reason": tactical.get("reason", "initial_pass")
        })
        
        return {
            "decision": decision,
            "mutation": tactical.get("suggested_mutation"),
            "params_override": {"mutation": tactical.get("suggested_mutation")} if decision == "MUTATE" else {}
        }

    def _emit_vrad_pulse(self, event_type: str, detail: Dict[str, Any]):
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type=event_type,
                    phase="adversarial_reflection",
                    detail=detail
                )
            )
        except Exception:
            pass

    def reflect_on_failure(
        self, 
        playbook_id: str, 
        raw_output: str, 
        error: str, 
        target_fingerprint: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Failure Reflector (RECOVERY ENGINE):
        Performs post-mortem on tool output.
        """
        combined = (raw_output + " " + error).lower()
        
        reflection = {
            "playbook_id": playbook_id,
            "detected_block": None,
            "reflection": "",
            "suggested_mutation": None
        }

        if "403" in combined or "forbidden" in combined or "cloudflare" in combined:
            reflection["detected_block"] = "WAF_BLOCK"
            reflection["reflection"] = "The WAF blocked the request based on fingerprinting."
            reflection["suggested_mutation"] = "user_agent_spoofing"
        elif "timeout" in combined or "deadline" in combined:
            reflection["detected_block"] = "TIMEOUT"
            reflection["reflection"] = "Tool timed out. Likely rate limiting or deep packet inspection."
            reflection["suggested_mutation"] = "chunked_transfer"
        elif "rate limit" in combined or "429" in combined:
            reflection["detected_block"] = "RATE_LIMIT"
            reflection["reflection"] = "Target is enforcing strict rate limits."
            reflection["suggested_mutation"] = "randomized_timing"

        return reflection if reflection["detected_block"] else None
