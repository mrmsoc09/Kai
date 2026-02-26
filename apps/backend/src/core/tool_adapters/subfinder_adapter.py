"""
Subfinder Tool Adapter
Fast passive subdomain discovery
"""

import asyncio
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any

from .base_adapter import (
    BaseToolAdapter,
    ToolCategory,
    ToolTier,
    CapabilityType,
    ToolExecutionResult,
    ToolCapability
)


class SubfinderAdapter(BaseToolAdapter):
    """
    Subfinder - Fast passive subdomain enumeration

    Capabilities:
    - Passive subdomain discovery
    - Multiple source integration
    - Fast enumeration

    Tiers:
    - Community: Basic passive enumeration
    - Pro: API keys for enhanced sources
    """

    def get_tool_name(self) -> str:
        return "subfinder"

    def get_tool_category(self) -> ToolCategory:
        return ToolCategory.DOMAIN_INFRASTRUCTURE

    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                capability_type=CapabilityType.SUBDOMAIN_ENUMERATION,
                confidence=0.90,
                description="Fast passive subdomain discovery",
                tier_required=ToolTier.COMMUNITY
            ),
            ToolCapability(
                capability_type=CapabilityType.DNS_RECONNAISSANCE,
                confidence=0.85,
                description="DNS enumeration via passive sources",
                tier_required=ToolTier.COMMUNITY
            )
        ]

    async def check_availability(self) -> bool:
        """Check if subfinder is installed"""
        return shutil.which("subfinder") is not None

    async def execute(
        self,
        target: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """Execute subfinder against target"""
        started_at = datetime.utcnow()
        options = options or {}

        cmd = ["subfinder", "-d", target, "-json", "-silent"]

        # Options
        if options.get("recursive"):
            cmd.append("-recursive")
        if options.get("all"):
            cmd.append("-all")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            raw_output = stdout.decode()
            findings = self.parse_output_to_findings(raw_output, target)

            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                findings=findings,
                raw_output=raw_output,
                structured_output={
                    "subdomains": [f["subdomain"] for f in findings],
                    "total_subdomains": len(findings)
                },
                command_executed=" ".join(cmd),
                exit_code=proc.returncode
            )

        except Exception as e:
            completed_at = datetime.utcnow()
            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
                error_message=str(e)
            )

    def parse_output_to_findings(self, raw_output: str, target: str) -> List[Dict[str, Any]]:
        """Parse subfinder JSON output"""
        findings = []
        for line in raw_output.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                findings.append({
                    "type": "subdomain",
                    "subdomain": data.get("host", ""),
                    "domain": target,
                    "source": data.get("source", ""),
                    "discovered_at": datetime.utcnow().isoformat()
                })
            except Exception:
                continue
        return findings
