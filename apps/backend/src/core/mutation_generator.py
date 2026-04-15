from __future__ import annotations

import random
from typing import Any, Dict, List

class MutationGenerator:
    """
    K1 Mutation Generator (Phase 2).
    Applies tactical changes to InstructionTuples to bypass filters.
    """

    def mutate_instruction(
        self, 
        playbook_id: str, 
        params: Dict[str, Any], 
        timing: Dict[str, Any], 
        mutation_type: str
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Mutation Handshaking: returns updated params and timing.
        """
        new_params = dict(params)
        new_timing = dict(timing)

        if mutation_type == "user_agent_spoofing":
            mobile_agents = [
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
                "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
            ]
            new_params["user_agent"] = random.choice(mobile_agents)
            new_params["mutation"] = "ua_mobile_spoof"

        elif mutation_type == "chunked_transfer":
            new_params["http_transfer_encoding"] = "chunked"
            new_params["mutation"] = "chunked_evasion"

        elif mutation_type == "randomized_timing":
            new_timing["profile"] = "stealth"
            new_timing["delay_ms"] = random.randint(2000, 5000)
            new_params["request_rate"] = 1
            new_params["mutation"] = "jitter_timing"

        elif mutation_type == "hex_encoding":
            new_params["encoding"] = "hex"
            new_params["mutation"] = "hex_payload"

        return new_params, new_timing
