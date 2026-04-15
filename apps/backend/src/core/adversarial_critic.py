from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional, Tuple

from .experience_memory import ExperienceMemory

logger = logging.getLogger(__name__)

class AdversarialCritic:
    """
    K1 Adversarial Critic (Phase 2).
    Audits InstructionTuples and reflects on tool failures to suggest mutations.
    """

    def __init__(self, experience_memory: Optional[ExperienceMemory] = None) -> None:
        self.memory = experience_memory or ExperienceMemory.get_instance()

    def audit_instruction(
        self, 
        playbook_id: str, 
        params: Dict[str, Any], 
        target_fingerprint: Dict[str, Any]
    ) -> Tuple[Literal["APPROVE", "DENY", "MUTATE"], str]:
        """
        Pre-Flight Critic (OPSEC GUARDRAIL):
        Intercepts instruction before execution.
        """
        # 1. Check Experience Memory for WAF failures
        waf = target_fingerprint.get("waf", "unknown").lower()
        if "cloudflare" in waf and "sqli" in playbook_id.lower():
            return "MUTATE", "Cloudflare detected; standard SQLi payloads are likely to fail. Mutation required."

        # 2. Check for missing SNL status
        if not params.get("snl_interface"):
            return "DENY", "Instruction missing Sovereign Network Layer interface. Aborting for OPSEC."

        # 3. Check for high failure rate in history
        strategy = self.memory.recommend_strategy(
            target_fingerprint=target_fingerprint,
            attempted_cve=playbook_id
        )
        if strategy.get("failure_rate", 0.0) > 0.8:
            return "MUTATE", f"High historical failure rate ({strategy['failure_rate']}). Standard execution blocked."

        return "APPROVE", "Instruction matches safety profile."

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
