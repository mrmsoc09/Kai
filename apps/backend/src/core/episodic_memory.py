"""
K1 Episodic Memory System
Tracks agent attempts to prevent loops and waste
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json


class AttemptOutcome(str, Enum):
    """Outcome of attack attempt"""
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"
    DETECTION = "detection"
    UNKNOWN = "unknown"


@dataclass
class AttackAttempt:
    """Single attack attempt on a target"""
    attempt_id: str
    agent_id: str
    timestamp: datetime
    target_domain: str
    endpoint: str
    vulnerability_type: str
    technique: str  # Specific technique used
    payload_hash: str  # Hash of payload for deduplication
    outcome: AttemptOutcome
    response_code: Optional[int] = None
    response_headers: Optional[Dict] = None
    error_message: Optional[str] = None
    time_to_block: Optional[int] = None  # Seconds before blocked
    api_credits_used: float = 0.0
    confidence_before: float = 0.5  # Agent's confidence before attempt
    learned_from: str = ""  # What was learned


@dataclass
class EpisodicMemoryEntry:
    """Entry in agent's episodic memory"""
    memory_id: str
    agent_id: str
    target_domain: str
    endpoint: str
    vulnerability_type: str
    attempts: List[AttackAttempt] = field(default_factory=list)
    successful_techniques: List[str] = field(default_factory=list)
    failed_techniques: List[str] = field(default_factory=list)
    blocked_techniques: List[str] = field(default_factory=list)
    last_attempt: Optional[datetime] = None
    total_attempts: int = 0
    success_count: int = 0
    learned_patterns: List[str] = field(default_factory=list)
    estimated_difficulty: float = 0.5  # 0-1, how hard this target is


class EpisodicMemorySystem:
    """Manages episodic memory for agents"""

    def __init__(self):
        # agent_id -> target_domain -> endpoint -> memory
        self.memory: Dict[str, Dict[str, Dict[str, EpisodicMemoryEntry]]] = {}
        self.all_attempts: List[AttackAttempt] = []
        self.agent_learning_curves: Dict[str, Dict[str, int]] = {}  # agent -> (attempts per day)

    def record_attempt(
        self,
        agent_id: str,
        target_domain: str,
        endpoint: str,
        vulnerability_type: str,
        technique: str,
        payload_hash: str,
        outcome: AttemptOutcome,
        response_code: Optional[int] = None,
        error_message: Optional[str] = None,
        api_credits_used: float = 0.0,
        confidence_before: float = 0.5
    ) -> AttackAttempt:
        """Record a single attack attempt"""

        attempt = AttackAttempt(
            attempt_id=f"attempt_{len(self.all_attempts)}",
            agent_id=agent_id,
            timestamp=datetime.utcnow(),
            target_domain=target_domain,
            endpoint=endpoint,
            vulnerability_type=vulnerability_type,
            technique=technique,
            payload_hash=payload_hash,
            outcome=outcome,
            response_code=response_code,
            error_message=error_message,
            api_credits_used=api_credits_used,
            confidence_before=confidence_before
        )

        # Store attempt
        self.all_attempts.append(attempt)

        # Get or create memory entry
        if agent_id not in self.memory:
            self.memory[agent_id] = {}
        if target_domain not in self.memory[agent_id]:
            self.memory[agent_id][target_domain] = {}

        key = endpoint
        if key not in self.memory[agent_id][target_domain]:
            self.memory[agent_id][target_domain][key] = EpisodicMemoryEntry(
                memory_id=f"mem_{agent_id}_{target_domain}_{key[:20]}",
                agent_id=agent_id,
                target_domain=target_domain,
                endpoint=endpoint,
                vulnerability_type=vulnerability_type
            )

        entry = self.memory[agent_id][target_domain][key]
        entry.attempts.append(attempt)
        entry.total_attempts += 1
        entry.last_attempt = attempt.timestamp

        # Track techniques
        if outcome == AttemptOutcome.SUCCESS:
            entry.successful_techniques.append(technique)
            entry.success_count += 1
        elif outcome in [AttemptOutcome.BLOCKED, AttemptOutcome.RATE_LIMITED, AttemptOutcome.DETECTION]:
            entry.blocked_techniques.append(technique)
        else:
            entry.failed_techniques.append(technique)

        # Update difficulty estimate
        if entry.total_attempts > 0:
            entry.estimated_difficulty = 1.0 - (entry.success_count / entry.total_attempts)

        return attempt

    def should_retry_technique(
        self,
        agent_id: str,
        target_domain: str,
        endpoint: str,
        technique: str
    ) -> Tuple[bool, str]:
        """Check if technique should be retried"""

        key = endpoint
        if (agent_id not in self.memory or
            target_domain not in self.memory[agent_id] or
            key not in self.memory[agent_id][target_domain]):
            return True, "No previous attempts recorded"

        entry = self.memory[agent_id][target_domain][key]

        # Check if technique already tried recently
        recent_attempts = [a for a in entry.attempts
                          if a.technique == technique and
                          (datetime.utcnow() - a.timestamp).seconds < 3600]  # Last hour

        if recent_attempts:
            return False, f"Technique tried {len(recent_attempts)} times in last hour"

        # Check if technique succeeded before
        successful = [a for a in entry.attempts if a.technique == technique and a.outcome == AttemptOutcome.SUCCESS]
        if successful:
            return True, "Technique has succeeded before"

        # Check if technique was blocked
        blocked = [a for a in entry.attempts if a.technique == technique and a.outcome in [
            AttemptOutcome.BLOCKED, AttemptOutcome.RATE_LIMITED, AttemptOutcome.DETECTION
        ]]
        if blocked:
            return False, f"Technique blocked/rate-limited {len(blocked)} times"

        # Check failure rate
        failures = [a for a in entry.attempts if a.technique == technique]
        if failures and len([a for a in failures if a.outcome == AttemptOutcome.FAILED]) / len(failures) > 0.8:
            return False, f"Technique has {len([a for a in failures if a.outcome == AttemptOutcome.FAILED])}/{len(failures)} failure rate"

        return True, "No blocking conditions found"

    def get_target_history(
        self,
        agent_id: str,
        target_domain: str
    ) -> Dict[str, Any]:
        """Get complete history for target"""

        if (agent_id not in self.memory or
            target_domain not in self.memory[agent_id]):
            return {
                "agent_id": agent_id,
                "target_domain": target_domain,
                "total_attempts": 0,
                "endpoints": []
            }

        endpoints = []
        total_attempts = 0

        for endpoint, entry in self.memory[agent_id][target_domain].items():
            total_attempts += entry.total_attempts
            endpoints.append({
                "endpoint": endpoint,
                "vulnerability_type": entry.vulnerability_type,
                "total_attempts": entry.total_attempts,
                "successful": entry.success_count,
                "success_rate": (entry.success_count / entry.total_attempts * 100) if entry.total_attempts > 0 else 0,
                "estimated_difficulty": entry.estimated_difficulty,
                "successful_techniques": entry.successful_techniques,
                "blocked_techniques": entry.blocked_techniques
            })

        return {
            "agent_id": agent_id,
            "target_domain": target_domain,
            "total_attempts": total_attempts,
            "endpoints": endpoints
        }

    def get_learned_patterns(
        self,
        agent_id: str,
        vulnerability_type: str
    ) -> List[str]:
        """Get learned patterns for vulnerability type across all targets"""

        patterns = []

        if agent_id not in self.memory:
            return patterns

        for target_domain in self.memory[agent_id]:
            for endpoint, entry in self.memory[agent_id][target_domain].items():
                if entry.vulnerability_type == vulnerability_type:
                    # What worked?
                    if entry.successful_techniques:
                        patterns.append(f"On {target_domain}: {', '.join(entry.successful_techniques)} successful")
                    # What failed?
                    if entry.blocked_techniques:
                        patterns.append(f"On {target_domain}: {', '.join(entry.blocked_techniques)} blocked")

        return patterns

    def recommend_next_technique(
        self,
        agent_id: str,
        target_domain: str,
        endpoint: str,
        available_techniques: List[str],
        vulnerability_type: str
    ) -> Tuple[Optional[str], str]:
        """Recommend next technique based on history"""

        key = endpoint
        if (agent_id not in self.memory or
            target_domain not in self.memory[agent_id] or
            key not in self.memory[agent_id][target_domain]):
            # No history, recommend first technique
            return available_techniques[0] if available_techniques else None, "No history, fresh attempt"

        entry = self.memory[agent_id][target_domain][key]

        # Recommendation logic:
        # 1. Try successful techniques again
        # 2. Try new techniques not attempted
        # 3. Try variants of techniques that were blocked

        # Already successful?
        for technique in available_techniques:
            if technique in entry.successful_techniques:
                return technique, "Known successful technique"

        # Not attempted?
        attempted = set(entry.successful_techniques + entry.failed_techniques + entry.blocked_techniques)
        for technique in available_techniques:
            if technique not in attempted:
                return technique, "Novel technique not previously attempted"

        # Check for blockable techniques (might need variant)
        for technique in available_techniques:
            if technique in entry.blocked_techniques:
                return technique, "Try variant of blocked technique"

        # Fallback
        return available_techniques[0] if available_techniques else None, "Fallback to first available"

    def get_wasted_api_credits(
        self,
        agent_id: str,
        target_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get API credits wasted on repeated failed attempts"""

        if target_domain:
            attempts = []
            if agent_id in self.memory and target_domain in self.memory[agent_id]:
                for endpoint, entry in self.memory[agent_id][target_domain].items():
                    attempts.extend(entry.attempts)
        else:
            attempts = [a for a in self.all_attempts if a.agent_id == agent_id]

        failed_attempts = [a for a in attempts if a.outcome in [
            AttemptOutcome.FAILED, AttemptOutcome.BLOCKED, AttemptOutcome.RATE_LIMITED
        ]]

        total_wasted = sum(a.api_credits_used for a in failed_attempts)

        # Identify repeated techniques
        technique_attempts = {}
        for attempt in failed_attempts:
            key = f"{attempt.target_domain}:{attempt.endpoint}:{attempt.technique}"
            if key not in technique_attempts:
                technique_attempts[key] = []
            technique_attempts[key].append(attempt)

        repeated = {k: v for k, v in technique_attempts.items() if len(v) > 1}
        repeated_waste = sum(sum(a.api_credits_used for a in v) for v in repeated.values())

        return {
            "total_failed_attempts": len(failed_attempts),
            "total_api_credits_wasted": total_wasted,
            "repeated_technique_attempts": len(repeated),
            "wasted_on_repetition": repeated_waste,
            "potential_savings_percentage": (repeated_waste / total_wasted * 100) if total_wasted > 0 else 0
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        total_attempts = len(self.all_attempts)
        successful = len([a for a in self.all_attempts if a.outcome == AttemptOutcome.SUCCESS])

        return {
            "total_agents": len(self.memory),
            "total_targets": sum(len(targets) for targets in self.memory.values()),
            "total_attempts": total_attempts,
            "successful_attempts": successful,
            "success_rate": (successful / total_attempts * 100) if total_attempts > 0 else 0,
            "blocked_attempts": len([a for a in self.all_attempts if a.outcome == AttemptOutcome.BLOCKED]),
            "rate_limited": len([a for a in self.all_attempts if a.outcome == AttemptOutcome.RATE_LIMITED])
        }


# Global instance
episodic_memory = None


def initialize_episodic_memory() -> EpisodicMemorySystem:
    """Initialize episodic memory system"""
    global episodic_memory

    episodic_memory = EpisodicMemorySystem()
    print("✓ Episodic memory system initialized")

    return episodic_memory
