"""State management for fuzzing campaigns"""
from enum import Enum
from typing import Dict, Set, Optional
from dataclasses import dataclass, field
import time


class AttemptStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


@dataclass
class Attempt:
    payload: str
    timestamp: float = field(default_factory=time.time)
    status: AttemptStatus = AttemptStatus.PENDING
    response_time: float = 0.0
    response_data: Optional[str] = None
    error_message: Optional[str] = None


class CampaignState:
    """Manages state for an active fuzzing campaign"""
    
    def __init__(self):
        self.attempts: Dict[str, Attempt] = {}
        self.successful_payloads: Set[str] = set()
        self.blocked_ips: Set[str] = set()
        self.start_time: float = time.time()
        self.total_requests: int = 0
        self.active_connections: int = 0
        
    def register_attempt(self, attempt_id: str, payload: str) -> Attempt:
        attempt = Attempt(payload=payload)
        self.attempts[attempt_id] = attempt
        self.total_requests += 1
        return attempt
    
    def update_attempt(self, attempt_id: str, status: AttemptStatus, 
                      response_time: float = 0.0, data: Optional[str] = None):
        if attempt_id in self.attempts:
            attempt = self.attempts[attempt_id]
            attempt.status = status
            attempt.response_time = response_time
            attempt.response_data = data
            
            if status == AttemptStatus.SUCCESS:
                self.successful_payloads.add(attempt.payload)
    
    def get_success_rate(self) -> float:
        if not self.attempts:
            return 0.0
        successes = sum(1 for a in self.attempts.values() if a.status == AttemptStatus.SUCCESS)
        return successes / len(self.attempts)
    
    def get_average_response_time(self) -> float:
        completed = [a.response_time for a in self.attempts.values() 
                    if a.status != AttemptStatus.PENDING]
        return sum(completed) / len(completed) if completed else 0.0
