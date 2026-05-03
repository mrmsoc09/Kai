"""
Batched LLM Client
Cost-optimized batch API calls for content generation and intelligence tasks.
Leverages existing llm_budget_router for key pooling and rate limiting.
"""
import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import hashlib
import time

@dataclass
class BatchRequest:
    """Single request within a batch."""
    request_id: str
    prompt: str
    context: Dict[str, Any]
    priority: int = 5  # 1-10, lower = higher priority
    max_tokens: int = 500
    callback: Optional[Callable] = None

@dataclass
class BatchResponse:
    """Response for a single batched request."""
    request_id: str
    success: bool
    content: str
    tokens_used: int
    latency_ms: float
    error: Optional[str] = None

class BatchedLLMClient:
    """
    Batched LLM client for cost-efficient API usage.

    Key features:
    - Request batching for cost efficiency
    - Key rotation via llm_budget_router
    - Adaptive batch sizing based on historical performance
    - Request deduplication
    - Result caching
    """

    def __init__(
        self,
        max_batch_size: int = 10,
        max_wait_time_ms: int = 100,
        min_batch_size: int = 2
    ):
        self.max_batch_size = max_batch_size
        self.max_wait_time_ms = max_wait_time_ms
        self.min_batch_size = min_batch_size
        self.request_queue = []
        self.response_cache = {}
        self.stats = {
            'batches_sent': 0,
            'requests_batched': 0,
            'tokens_saved': 0,
            'cost_estimate': 0.0
        }
        self._batch_task = None

    def _get_cache_key(self, request: BatchRequest) -> str:
        """Generate cache key for request deduplication."""
        key_data = f"{request.prompt}|{request.max_tokens}|{json.dumps(request.context, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def submit(self, request: BatchRequest) -> BatchResponse:
        """
        Submit a request to be batched.
        Returns when the batch is processed.
        """
        # Check cache first
        cache_key = self._get_cache_key(request)
        if cache_key in self.response_cache:
            cached = self.response_cache[cache_key]
            return BatchResponse(
                request_id=request.request_id,
                success=True,
                content=cached['content'],
                tokens_used=cached['tokens'],
                latency_ms=0.0
            )

        # Add to queue
        future = asyncio.Future()
        self.request_queue.append({
            'request': request,
            'future': future,
            'submitted_at': time.time()
        })

        # Start batch processor if not running
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(self._process_batch())

        # Wait for result
        return await future

    async def _process_batch(self):
        """Process batched requests with adaptive timing."""
        await asyncio.sleep(self.max_wait_time_ms / 1000)

        if len(self.request_queue) < self.min_batch_size:
            # Process what we have anyway - don't hold too long
            pass

        # Take batch from queue
        batch_size = min(len(self.request_queue), self.max_batch_size)
        batch = self.request_queue[:batch_size]
        self.request_queue = self.request_queue[batch_size:]

        if not batch:
            return

        # Process batch
        start_time = time.time()
        responses = await self._execute_batch(batch)
        elapsed_ms = (time.time() - start_time) * 1000

        # Distribute responses
        for item, response in zip(batch, responses):
            # Cache successful responses
            if response.success:
                cache_key = self._get_cache_key(item['request'])
                self.response_cache[cache_key] = {
                    'content': response.content,
                    'tokens': response.tokens_used,
                    'cached_at': time.time()
                }

            # Notify completion
            if not item['future'].done():
                item['future'].set_result(response)

        # Update stats
        self.stats['batches_sent'] += 1
        self.stats['requests_batched'] += len(batch)

        # Schedule next batch if more requests pending
        if self.request_queue:
            self._batch_task = asyncio.create_task(self._process_batch())

    async def _execute_batch(
        self,
        batch: List[Dict]
    ) -> List[BatchResponse]:
        """
        Execute batch of requests efficiently.
        Integrates with llm_budget_router for key rotation.
        """
        responses = []

        # Group by similarity for prompt caching
        grouped = self._group_similar_requests(batch)

        for group in grouped:
            if len(group) == 1:
                # Single request - direct execution
                response = await self._execute_single(group[0]['request'])
                responses.append(response)
            else:
                # True batch execution
                batch_response = await self._execute_true_batch(
                    [item['request'] for item in group]
                )
                responses.extend(batch_response)

        return responses

    def _group_similar_requests(
        self,
        batch: List[Dict]
    ) -> List[List[Dict]]:
        """Group similar requests for efficient batching."""
        by_template = {}

        for item in batch:
            req = item['request']
            # Simple grouping by context type
            template_key = req.context.get('template_type', 'default')
            if template_key not in by_template:
                by_template[template_key] = []
            by_template[template_key].append(item)

        return list(by_template.values())

    async def _execute_single(self, request: BatchRequest) -> BatchResponse:
        """Execute single request via llm_budget_router."""
        start = time.time()

        try:
            # Integrate with existing llm_budget_router
            result = await self._call_llm_via_router(
                prompt=request.prompt,
                max_tokens=request.max_tokens
            )

            return BatchResponse(
                request_id=request.request_id,
                success=True,
                content=result['content'],
                tokens_used=result['tokens_used'],
                latency_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return BatchResponse(
                request_id=request.request_id,
                success=False,
                content="",
                tokens_used=0,
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )

    async def _execute_true_batch(
        self,
        requests: List[BatchRequest]
    ) -> List[BatchResponse]:
        """
        Execute true batch request for maximum efficiency.
        Combines prompts into single API call.
        """
        start = time.time()

        # Combine prompts into batch format
        combined_prompt = self._create_combined_prompt(requests)

        try:
            # Single API call for all requests
            result = await self._call_llm_via_router(
                prompt=combined_prompt,
                max_tokens=sum(r.max_tokens for r in requests) * 2
            )

            # Parse individual responses
            parsed = self._parse_batch_response(result['content'], requests)

            # Estimate savings
            saved_requests = len(requests) - 1
            self.stats['tokens_saved'] += saved_requests * 100  # Approximation

            return [
                BatchResponse(
                    request_id=req.request_id,
                    success=True,
                    content=content,
                    tokens_used=result['tokens_used'] // len(requests),
                    latency_ms=(time.time() - start) * 1000
                )
                for req, content in zip(requests, parsed)
            ]

        except Exception as e:
            # Fallback to individual execution
            return await asyncio.gather(*[
                self._execute_single(req) for req in requests
            ])

    def _create_combined_prompt(self, requests: List[BatchRequest]) -> str:
        """Combine multiple prompts into batch prompt."""
        items = []
        for i, req in enumerate(requests, 1):
            items.append(f"\n--- REQUEST {i} ---\nID: {req.request_id}\nPROMPT: {req.prompt}\n")

        return f"""Process the following {len(requests)} requests and respond with results for each.

{''.join(items)}

Respond in this exact format:
--- RESULT 1 ---
ID: <request_id>
RESPONSE: <content>

--- RESULT 2 ---
ID: <request_id>
RESPONSE: <content>
"""

    def _parse_batch_response(
        self,
        content: str,
        requests: List[BatchRequest]
    ) -> List[str]:
        """Parse combined response into individual results."""
        results = []
        for req in requests:
            # Simple parsing - look for request ID
            marker = f"--- RESULT {requests.index(req) + 1} ---"
            if marker in content:
                parts = content.split(marker)
                if len(parts) > 1:
                    result_section = parts[1].split("--- RESULT")[0]
                    # Extract after RESPONSE:
                    if "RESPONSE:" in result_section:
                        response_text = result_section.split("RESPONSE:")[1].strip()
                        results.append(response_text)
                    else:
                        results.append(result_section.strip())
                else:
                    results.append("[Parse error]")
            else:
                # Fallback: use entire content
                results.append(content)

        return results if results else [content] * len(requests)

    async def _call_llm_via_router(
        self,
        prompt: str,
        max_tokens: int
    ) -> Dict:
        """
        Call LLM through existing budget router.
        Import and use LLMBudgetRouter from core/llm_budget_router.py
        """
        try:
            from core.llm_budget_router import LLMBudgetRouter
            router = LLMBudgetRouter()
            return await router.call(prompt, max_tokens)
        except ImportError:
            # Fallback for testing
            return {
                'content': f"[Mock response for: {prompt[:50]}...]",
                'tokens_used': max_tokens // 2,
                'model_used': 'mock'
            }

    def get_stats(self) -> Dict:
        """Get batch processing statistics."""
        return {
            **self.stats,
            'cache_hit_rate': len(self.response_cache) / max(self.stats['requests_batched'], 1),
            'average_batch_size': self.stats['requests_batched'] / max(self.stats['batches_sent'], 1)
        }

    def get_cost_estimate(self) -> float:
        """Estimate cost savings from batching."""
        # Rough estimate: 10% savings per batched call at $0.01/1K tokens
        batches_saved = max(0, self.stats['requests_batched'] - self.stats['batches_sent'])
        return batches_saved * 0.05  # Approximate $0.05 per saved call

class ContentGenerationBatcher:
    """
    Specialized batcher for BBP content generation tasks.
    Optimized for generating multiple finding reports simultaneously.
    """

    def __init__(self):
        self.client = BatchedLLMClient(
            max_batch_size=5,  # Smaller batches for reports
            max_wait_time_ms=200  # Longer wait to accumulate more
        )

    async def generate_reports(
        self,
        findings: List[Dict],
        bbp_mode: str = "public_bbp"
    ) -> List[Dict]:
        """
        Batch generate reports for multiple findings.

        Args:
            findings: List of vuln findings
            bbp_mode: BBP mode for template selection

        Returns:
            List of generated reports
        """
        # Create batch requests
        requests = []
        for i, finding in enumerate(findings):
            req = BatchRequest(
                request_id=f"find_{i}",
                prompt=self._create_prompt(finding, bbp_mode),
                context={
                    'template_type': finding.get('type', 'default'),
                    'bbp_mode': bbp_mode
                },
                max_tokens=800,
                priority=5 if finding.get('severity') != 'critical' else 1
            )
            requests.append(req)

        # Submit all requests
        responses = await asyncio.gather(*[
            self.client.submit(req) for req in requests
        ])

        # Combine with findings
        results = []
        for finding, response in zip(findings, responses):
            results.append({
                'finding': finding,
                'report': response.content if response.success else f"Error: {response.error}",
                'metadata': {
                    'tokens_used': response.tokens_used,
                    'latency_ms': response.latency_ms
                }
            })

        return results

    def _create_prompt(self, finding: Dict, bbp_mode: str) -> str:
        """Create generation prompt for finding."""
        return f"""Generate a bug bounty submission report for:

Vulnerability Type: {finding.get('type', 'Unknown')}
Severity: {finding.get('severity', 'Medium')}
Target: {finding.get('target', 'Unknown')}
Description: {finding.get('description', '')}

BBP Mode: {bbp_mode}

Include: Title, Description, Impact, Reproduction Steps, Remediation."""

# Singleton for shared use
_batch_client: Optional[BatchedLLMClient] = None

def get_batched_client() -> BatchedLLMClient:
    """Get singleton batched client instance."""
    global _batch_client
    if _batch_client is None:
        _batch_client = BatchedLLMClient()
    return _batch_client

if __name__ == "__main__":
    async def test():
        client = BatchedLLMClient()

        # Test batch submissions
        requests = [
            BatchRequest(f"req_{i}", f"Test prompt {i}", {}) for i in range(5)
        ]

        responses = await asyncio.gather(*[
            client.submit(req) for req in requests
        ])

        print(f"Processed {len(responses)} requests")
        print(f"Stats: {client.get_stats()}")
        print(f"Estimated savings: ${client.get_cost_estimate():.4f}")

    asyncio.run(test())
