"""Core fuzzing engine with async support"""
import asyncio
import time
import uuid
from typing import Optional, Callable, AsyncIterator, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import logging

from .config import Config
from .state import CampaignState, AttemptStatus
from ..protocols.base import BaseProtocolHandler
from ..wordlists.generator import WordlistGenerator
from ..evasion.timing import AdaptiveTimingController
from ..evasion.waf import WAFEvasion
from ..ai.feedback import AIFeedbackLoop
from ..utils.stats import StatisticsCollector
from ..utils.logger import setup_logger


class FuzzingEngine:
    """
    High-performance async fuzzing engine with AI-driven optimization
    """
    
    def __init__(self, config: Config, protocol_handler: BaseProtocolHandler):
        self.config = config
        self.protocol = protocol_handler
        self.state = CampaignState()
        self.stats = StatisticsCollector()
        self.logger = setup_logger(config.log_level, config.log_file)
        
        # Advanced components
        self.timing_controller = AdaptiveTimingController(config)
        self.waf_evasion = WAFEvasion(config) if config.waf_evasion_enabled else None
        self.ai_feedback = AIFeedbackLoop(config) if config.ai_mutation_enabled else None
        
        # Async components
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.queue: Optional[asyncio.Queue] = None
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize async resources"""
        self.semaphore = asyncio.Semaphore(self.config.max_workers)
        self.queue = asyncio.Queue(maxsize=self.config.max_workers * 2)
        self.logger.info(f"Initialized FuzzingEngine with {self.config.max_workers} workers")
        
    async def shutdown(self):
        """Graceful shutdown"""
        self._shutdown_event.set()
        if self.queue:
            await self.queue.join()
        self.logger.info("Engine shutdown complete")
        
    async def _worker(self, worker_id: int):
        """Worker coroutine for processing payloads"""
        while not self._shutdown_event.is_set():
            try:
                attempt_id, payload = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
                
            async with self.semaphore:
                await self._execute_attempt(attempt_id, payload)
                self.queue.task_done()
                
    async def _execute_attempt(self, attempt_id: str, payload: str):
        """Execute single fuzzing attempt with evasion and timing"""
        start_time = time.time()
        self.state.active_connections += 1
        
        try:
            # Apply WAF evasion if enabled
            if self.waf_evasion:
                payload = self.waf_evasion.obfuscate(payload)
                
            # Adaptive delay
            await self.timing_controller.delay()
            
            # Execute protocol-specific request
            result = await self.protocol.execute(payload)
            
            response_time = time.time() - start_time
            
            # Determine status
            if result.success:
                status = AttemptStatus.SUCCESS
                self.stats.record_success(payload, response_time)
                if self.ai_feedback:
                    self.ai_feedback.report_success(payload, result.data)
            else:
                status = AttemptStatus.FAILURE
                if result.blocked:
                    status = AttemptStatus.BLOCKED
                    self.timing_controller.report_block()
                    
            self.state.update_attempt(attempt_id, status, response_time, result.data)
            
        except asyncio.TimeoutError:
            self.state.update_attempt(attempt_id, AttemptStatus.TIMEOUT, time.time() - start_time)
            self.timing_controller.report_timeout()
        except Exception as e:
            self.logger.error(f"Attempt {attempt_id} failed: {e}")
            self.state.update_attempt(attempt_id, AttemptStatus.FAILURE, error_message=str(e))
        finally:
            self.state.active_connections -= 1
            
    async def _producer(self, generator: WordlistGenerator):
        """Produce payloads from wordlist generator"""
        count = 0
        
        async for payload in generator.generate():
            if self._shutdown_event.is_set():
                break
                
            attempt_id = str(uuid.uuid4())
            self.state.register_attempt(attempt_id, payload)
            
            # AI-driven mutation feedback
            if self.ai_feedback and count % self.config.feedback_loop_interval == 0:
                mutated = self.ai_feedback.mutate_payload(payload)
                if mutated != payload:
                    await self.queue.put((str(uuid.uuid4()), mutated))
            
            await self.queue.put((attempt_id, payload))
            count += 1
            
            # Real-time stats update
            if count % 100 == 0:
                self._log_progress()
                
        # Signal completion
        await self.queue.join()
        
    def _log_progress(self):
        """Log current progress statistics"""
        elapsed = time.time() - self.state.start_time
        rps = self.state.total_requests / elapsed if elapsed > 0 else 0
        success_rate = self.state.get_success_rate() * 100
        
        self.logger.info(
            f"Progress: {self.state.total_requests} reqs | "
            f"{rps:.2f} req/s | Success: {success_rate:.2f}% | "
            f"Active: {self.state.active_connections}"
        )
        
    async def run(self, generator: WordlistGenerator, duration: Optional[float] = None):
        """
        Main execution loop
        
        Args:
            generator: Wordlist generator instance
            duration: Optional max duration in seconds
        """
        await self.initialize()
        
        # Start workers
        workers = [
            asyncio.create_task(self._worker(i)) 
            for i in range(self.config.max_workers)
        ]
        
        # Start producer
        producer_task = asyncio.create_task(self._producer(generator))
        
        # Optional timeout
        if duration:
            producer_task = asyncio.wait_for(producer_task, timeout=duration)
            
        try:
            await producer_task
        except asyncio.TimeoutError:
            self.logger.info("Campaign reached time limit")
        finally:
            await self.shutdown()
            for w in workers:
                w.cancel()
                
        return self.state
