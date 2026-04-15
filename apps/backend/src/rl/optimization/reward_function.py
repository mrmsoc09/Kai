from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
import numpy as np

# Reward configuration constants
REWARD_PAYOUT_VERIFIED = 50.0
REWARD_EXPLOITATION_SUCCESS = 10.0
REWARD_ASSET_DISCOVERY = 2.0
PENALTY_WAF_BLOCK = -10.0
PENALTY_SNL_FAIL = -20.0
PENALTY_TIMEOUT = -5.0

@dataclass
class StrategicReward:
    """Calculates reward signals based on K1 execution outcomes."""
    
    def calculate_reward(self, outcome: str, metadata: Dict[str, Any]) -> float:
        """
        Calculates the scalar reward signal for the RL policy.
        """
        if outcome == "Bounty_Verified":
            return REWARD_PAYOUT_VERIFIED
        elif outcome == "Exploitation_Success":
            return REWARD_EXPLOITATION_SUCCESS
        elif outcome == "Asset_Discovery":
            return REWARD_ASSET_DISCOVERY
        elif outcome == "WAF_Block":
            return PENALTY_WAF_BLOCK
        elif outcome == "SNL_Failure":
            return PENALTY_SNL_FAIL
        elif outcome in ("Timeout", "Redundant"):
            return PENALTY_TIMEOUT
        return 0.0

    def compute_cumulative(self, outcomes: List[str]) -> float:
        return sum(self.calculate_reward(o, {}) for o in outcomes)
