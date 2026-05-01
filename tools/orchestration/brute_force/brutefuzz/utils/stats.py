"""Real-time statistics collection"""
import time
from typing import Dict, List
from dataclasses import dataclass, field
from collections import deque


@dataclass
class StatisticsCollector:
    """Thread-safe statistics collection"""
    
    start_time: float = field(default_factory=time.time)
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    blocked_requests: int = 0
    
    # Performance metrics
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    throughput_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Payload effectiveness
    payload_success: Dict[str, int] = field(default_factory=dict)
    
    def record_success(self, payload: str, response_time: float):
        self.total_requests += 1
        self.successful_requests += 1
        self.response_times.append(response_time)
        self.payload_success[payload] = self.payload_success.get(payload, 0) + 1
        
    def record_failure(self, blocked: bool = False):
        self.total_requests += 1
        self.failed_requests += 1
        if blocked:
            self.blocked_requests += 1
            
    def get_stats(self) -> Dict:
        """Get current statistics snapshot"""
        elapsed = time.time() - self.start_time
        rps = self.total_requests / elapsed if elapsed > 0 else 0
        
        avg_response = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        
        return {
            "elapsed_time": elapsed,
            "total_requests": self.total_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0,
            "requests_per_second": rps,
            "avg_response_time": avg_response,
            "active_blocks": self.blocked_requests,
            "top_payloads": sorted(self.payload_success.items(), 
                                 key=lambda x: x[1], reverse=True)[:5]
        }
