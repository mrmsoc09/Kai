"""
Amass Tool Adapter
Subdomain enumeration and network mapping
"""

import asyncio
import json
import shutil
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

from .base_adapter import (
    BaseToolAdapter,
    ToolCategory,
    ToolTier,
    CapabilityType,
    ToolExecutionResult,
    ToolCapability
)


class AmassAdapter(BaseToolAdapter):
    """
    Amass - In-depth attack surface mapping and asset discovery

    Capabilities:
    - Subdomain enumeration
    - DNS reconnaissance
    - Network mapping
    - ASN discovery

    Tiers:
    - Community: Basic features
    - Pro: API integrations (Shodan, Censys, etc.)
    """

    def get_tool_name(self) -> str:
        return "amass"

    def get_tool_category(self) -> ToolCategory:
        return ToolCategory.DOMAIN_INFRASTRUCTURE

    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                capability_type=CapabilityType.SUBDOMAIN_ENUMERATION,
                confidence=0.95,
                description="Industry-leading subdomain discovery",
                tier_required=ToolTier.COMMUNITY
            ),
            ToolCapability(
                capability_type=CapabilityType.DNS_RECONNAISSANCE,
                confidence=0.90,
                description="Comprehensive DNS enumeration",
                tier_required=ToolTier.COMMUNITY
            ),
            ToolCapability(
                capability_type=CapabilityType.CLOUD_ASSET_DISCOVERY,
                confidence=0.85,
                description="Cloud infrastructure discovery with API keys",
                tier_required=ToolTier.PRO
            )
        ]

    async def check_availability(self) -> bool:
        """Check if amass is installed"""
        amass_path = shutil.which("amass")
        if not amass_path:
            self.logger.warning("amass not found in PATH")
            return False

        # Check version
        try:
            proc = await asyncio.create_subprocess_exec(
                "amass", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()

            version = stdout.decode().strip()
            self.logger.info(f"amass version: {version}")
            return True

        except Exception as e:
            self.logger.error(f"Error checking amass: {str(e)}")
            return False

    def get_tier_available(self) -> ToolTier:
        """
        Detect if Pro features available (API keys configured)

        Pro features require API keys in config:
        - Shodan
        - Censys
        - VirusTotal
        - etc.
        """
        # Check for amass config with API keys
        config_paths = [
            Path.home() / ".config/amass/config.ini",
            Path.home() / ".amass/config.ini"
        ]

        for config_path in config_paths:
            if config_path.exists():
                content = config_path.read_text()
                # Check if any API keys configured
                if any(key in content for key in ["api_key", "apikey", "shodan", "censys"]):
                    return ToolTier.PRO

        return ToolTier.COMMUNITY

    async def execute(
        self,
        target: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Execute amass enum against target

        Args:
            target: Domain to enumerate
            options:
                - passive: Use passive mode only (default: False)
                - timeout: Timeout in minutes (default: 30)
                - resolvers: Custom DNS resolvers file path
                - config: Custom config file path

        Returns:
            ToolExecutionResult with subdomains
        """
        started_at = datetime.now(timezone.utc)
        options = options or {}

        # Validate target
        if not await self.validate_target(target):
            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_seconds=0,
                error_message="Invalid target"
            )

        # Build command
        cmd = ["amass", "enum"]

        # Passive mode
        if options.get("passive", False):
            cmd.append("-passive")

        # Domain
        cmd.extend(["-d", target])

        # Output format
        cmd.extend(["-json", "-"])

        # Timeout
        timeout_mins = options.get("timeout", 30)
        cmd.extend(["-timeout", str(timeout_mins)])

        # Custom resolvers
        if options.get("resolvers"):
            cmd.extend(["-rf", options["resolvers"]])

        # Custom config
        if options.get("config"):
            cmd.extend(["-config", options["config"]])

        self.logger.info(f"Executing: {' '.join(cmd)}")

        try:
            # Execute command
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Set timeout
            timeout_seconds = timeout_mins * 60 + 60  # Add buffer
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds
            )

            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            raw_output = stdout.decode()
            stderr_output = stderr.decode()

            # Parse findings
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
                exit_code=proc.returncode,
                warnings=[stderr_output] if stderr_output else []
            )

        except asyncio.TimeoutError:
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            self.logger.error(f"amass timed out after {timeout_mins} minutes")

            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                error_message=f"Timeout after {timeout_mins} minutes"
            )

        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            self.logger.error(f"amass execution failed: {str(e)}")

            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                error_message=str(e)
            )

    def parse_output_to_findings(
        self,
        raw_output: str,
        target: str
    ) -> List[Dict[str, Any]]:
        """
        Parse amass JSON output to findings

        amass outputs newline-delimited JSON:
        {"name":"subdomain.example.com","domain":"example.com","addresses":["1.2.3.4"],...}
        """
        findings = []

        for line in raw_output.strip().split("\n"):
            if not line.strip():
                continue

            try:
                data = json.loads(line)

                # Extract subdomain
                subdomain = data.get("name", "")
                if not subdomain:
                    continue

                finding = {
                    "type": "subdomain",
                    "subdomain": subdomain,
                    "domain": data.get("domain", target),
                    "addresses": data.get("addresses", []),
                    "tag": data.get("tag", ""),
                    "sources": data.get("sources", []),
                    "discovered_at": datetime.now(timezone.utc).isoformat()
                }

                findings.append(finding)

            except json.JSONDecodeError:
                self.logger.warning(f"Failed to parse JSON line: {line[:100]}")
                continue

        self.logger.info(f"Parsed {len(findings)} subdomains")
        return findings
