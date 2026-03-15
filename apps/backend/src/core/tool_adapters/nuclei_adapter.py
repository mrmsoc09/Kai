"""
Nuclei Tool Adapter
Fast and customizable vulnerability scanner
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


class NucleiAdapter(BaseToolAdapter):
    """
    Nuclei - Fast and customizable vulnerability scanner

    Capabilities:
    - DAST (Dynamic Application Security Testing)
    - API security testing
    - Misconfiguration detection
    - CVE detection

    Tiers:
    - Community: Public templates
    - Pro: Private templates + custom workflows
    """

    def get_tool_name(self) -> str:
        return "nuclei"

    def get_tool_category(self) -> ToolCategory:
        return ToolCategory.VULNERABILITY_SCANNING

    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                capability_type=CapabilityType.DAST,
                confidence=0.92,
                description="Dynamic vulnerability scanning with 5000+ templates",
                tier_required=ToolTier.COMMUNITY
            ),
            ToolCapability(
                capability_type=CapabilityType.API_SECURITY_TESTING,
                confidence=0.88,
                description="API endpoint security testing",
                tier_required=ToolTier.COMMUNITY
            ),
            ToolCapability(
                capability_type=CapabilityType.VULNERABILITY_VALIDATION,
                confidence=0.90,
                description="CVE and security misconfiguration detection",
                tier_required=ToolTier.COMMUNITY
            )
        ]

    async def check_availability(self) -> bool:
        """Check if nuclei is installed"""
        nuclei_path = shutil.which("nuclei")
        if not nuclei_path:
            self.logger.warning("nuclei not found in PATH")
            return False

        # Check version
        try:
            proc = await asyncio.create_subprocess_exec(
                "nuclei", "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()

            version = stdout.decode().strip()
            self.logger.info(f"nuclei version: {version}")

            # Ensure templates are updated
            self.logger.info("Updating nuclei templates...")
            update_proc = await asyncio.create_subprocess_exec(
                "nuclei", "-update-templates",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await update_proc.communicate()

            return True

        except Exception as e:
            self.logger.error(f"Error checking nuclei: {str(e)}")
            return False

    def get_tier_available(self) -> ToolTier:
        """
        Check for Pro features (custom templates directory)
        """
        # Check for custom templates
        custom_templates = Path.home() / ".nuclei-templates-custom"
        if custom_templates.exists():
            return ToolTier.PRO

        return ToolTier.COMMUNITY

    async def execute(
        self,
        target: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Execute nuclei scan against target

        Args:
            target: URL or domain to scan
            options:
                - severity: Comma-separated severity levels (critical,high,medium,low,info)
                - tags: Comma-separated tags (e.g., "cve,osint,tech")
                - templates: Custom template directory
                - rate_limit: Requests per second (default: 150)
                - timeout: Request timeout in seconds (default: 5)
                - retries: Number of retries (default: 1)

        Returns:
            ToolExecutionResult with vulnerabilities found
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
        cmd = ["nuclei", "-u", target]

        # JSON output
        cmd.extend(["-json", "-silent"])

        # Severity filter
        if options.get("severity"):
            cmd.extend(["-severity", options["severity"]])
        else:
            # Default: critical and high only for performance
            cmd.extend(["-severity", "critical,high"])

        # Tags filter
        if options.get("tags"):
            cmd.extend(["-tags", options["tags"]])

        # Custom templates
        if options.get("templates"):
            cmd.extend(["-t", options["templates"]])

        # Rate limiting
        rate_limit = options.get("rate_limit", 150)
        cmd.extend(["-rate-limit", str(rate_limit)])

        # Timeout
        timeout = options.get("timeout", 5)
        cmd.extend(["-timeout", str(timeout)])

        # Retries
        retries = options.get("retries", 1)
        cmd.extend(["-retries", str(retries)])

        # Disable interactsh for privacy
        cmd.append("-ni")

        self.logger.info(f"Executing: {' '.join(cmd)}")

        try:
            # Execute command
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait with timeout (max 30 minutes)
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=1800
            )

            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            raw_output = stdout.decode()
            stderr_output = stderr.decode()

            # Parse findings
            findings = self.parse_output_to_findings(raw_output, target)

            # Categorize by severity
            severity_counts = {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0
            }

            for finding in findings:
                severity = finding.get("severity", "info").lower()
                if severity in severity_counts:
                    severity_counts[severity] += 1

            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                findings=findings,
                raw_output=raw_output,
                structured_output={
                    "total_vulnerabilities": len(findings),
                    "severity_breakdown": severity_counts,
                    "target": target
                },
                command_executed=" ".join(cmd),
                exit_code=proc.returncode,
                warnings=[stderr_output] if stderr_output else []
            )

        except asyncio.TimeoutError:
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            self.logger.error("nuclei scan timed out after 30 minutes")

            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                error_message="Scan timeout after 30 minutes"
            )

        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            self.logger.error(f"nuclei execution failed: {str(e)}")

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
        Parse nuclei JSON output to findings

        Nuclei outputs newline-delimited JSON
        """
        findings = []

        for line in raw_output.strip().split("\n"):
            if not line.strip():
                continue

            try:
                data = json.loads(line)

                finding = {
                    "type": "vulnerability",
                    "template_id": data.get("template-id", ""),
                    "name": data.get("info", {}).get("name", ""),
                    "severity": data.get("info", {}).get("severity", "info"),
                    "description": data.get("info", {}).get("description", ""),
                    "tags": data.get("info", {}).get("tags", []),
                    "matched_at": data.get("matched-at", ""),
                    "matcher_name": data.get("matcher-name", ""),
                    "extracted_results": data.get("extracted-results", []),
                    "curl_command": data.get("curl-command", ""),
                    "cvss_score": data.get("info", {}).get("classification", {}).get("cvss-score", 0),
                    "cve_id": data.get("info", {}).get("classification", {}).get("cve-id", []),
                    "cwe_id": data.get("info", {}).get("classification", {}).get("cwe-id", []),
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "target": target
                }

                findings.append(finding)

            except json.JSONDecodeError:
                self.logger.warning(f"Failed to parse JSON line: {line[:100]}")
                continue

        self.logger.info(f"Parsed {len(findings)} vulnerabilities")
        return findings
