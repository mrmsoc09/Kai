"""Adaptive timing controls for rate limit evasion"""
import asyncio
import random
import time
from typing import Deque
from collections import deque


class AdaptiveTimingController:
    """
    Intelligent rate limiting with exponential backoff and jitter
    """
    
    def __init__(self, config):
        self.config = config
        self.min_delay = 1.0 / config.requests_per_second
        self.current_delay = self.min_delay
        self.max_delay = 60.0  # Cap at 1 minute
        
        # Statistics for adaptation
        self.recent_blocks: Deque[float] = deque(maxlen=10)
        self.recent_timeouts: Deque[float] = deque(maxlen=10)
        self.success_times: Deque[float] = deque(maxlen=100)
        
        self.last_request_time: float = 0
        
    async def delay(self):
        """Apply adaptive delay with jitter"""
        # Calculate base delay
        if self.config.adaptive_rate_limiting:
            # Increase delay if recent blocks
            if len(self.recent_blocks) > 2:
                self.current_delay = min(self.current_delay * 1.5, self.max_delay)
            # Decrease slowly on success
            elif len(self.success_times) > 10:
                self.current_delay = max(self.current_delay * 0.95, self.min_delay)
        
        # Add jitter to avoid pattern detection
        jitter = random.uniform(*self.config.jitter_range)
        actual_delay = self.current_delay + jitter
        
        # Ensure we don't exceed rate limit
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < actual_delay:
            await asyncio.sleep(actual_delay - time_since_last)
            
        self.last_request_time = time.time()
        
    def report_block(self):
        """Report a rate limit/block event"""
        self.recent_blocks.append(time.time())
        
    def report_timeout(self):
        """Report a timeout (possible block)"""
        self.recent_timeouts.append(time.time())
        
    def report_success(self, response_time: float):
        """Record successful request timing"""
        self.success_times.append(response_time)
