"""
TruffleHog Tool Adapter
Secret and credential scanner for git repositories and filesystems
"""

import asyncio
import json
import shutil
from datetime import datetime
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


class TruffleHogAdapter(BaseToolAdapter):
    """
    TruffleHog - Find credentials in git repositories and filesystems

    Capabilities:
    - Secret scanning (API keys, passwords, tokens)
    - Git history analysis
    - Filesystem scanning
    - Real-time verification of found secrets

    Tiers:
    - Community: Basic secret detection
    - Pro: Verification against live services
    """

    def get_tool_name(self) -> str:
        return "trufflehog"

    def get_tool_category(self) -> ToolCategory:
        return ToolCategory.CODE_METADATA_FILE

    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                capability_type=CapabilityType.SECRET_SCANNING,
                confidence=0.93,
                description="High-accuracy secret and credential detection",
                tier_required=ToolTier.COMMUNITY
            ),
            ToolCapability(
                capability_type=CapabilityType.CODE_ANALYSIS,
                confidence=0.85,
                description="Git history and source code analysis",
                tier_required=ToolTier.COMMUNITY
            )
        ]

    async def check_availability(self) -> bool:
        """Check if trufflehog is installed"""
        # Try trufflehog3 first (newer version)
        trufflehog_path = shutil.which("trufflehog") or shutil.which("trufflehog3")

        if not trufflehog_path:
            self.logger.warning("trufflehog not found in PATH")
            return False

        try:
            # Check if it's the new version (v3+)
            proc = await asyncio.create_subprocess_exec(
                "trufflehog", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            version_output = stdout.decode() + stderr.decode()
            self.logger.info(f"trufflehog version: {version_output.strip()}")

            return True

        except Exception as e:
            self.logger.error(f"Error checking trufflehog: {str(e)}")
            return False

    def get_tier_available(self) -> ToolTier:
        """
        Pro features require verification enabled
        """
        # TruffleHog v3+ has built-in verification
        # Check if verification is available
        return ToolTier.PRO  # Assume Pro by default for v3+

    async def execute(
        self,
        target: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Execute trufflehog scan

        Args:
            target: Git URL, GitHub org/repo, or filesystem path
            options:
                - scan_type: "git", "github", "filesystem" (auto-detect if not specified)
                - verify: Enable verification (default: True)
                - include_detectors: Specific detectors to include
                - exclude_detectors: Detectors to exclude
                - since_commit: Only scan commits after this
                - max_depth: Max commit depth (default: 10000)

        Returns:
            ToolExecutionResult with secrets found
        """
        started_at = datetime.utcnow()
        options = options or {}

        # Validate target
        if not await self.validate_target(target):
            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_seconds=0,
                error_message="Invalid target"
            )

        # Detect scan type
        scan_type = options.get("scan_type")
        if not scan_type:
            if target.startswith(("http://", "https://", "git@")):
                scan_type = "git"
            elif "github.com" in target:
                scan_type = "github"
            else:
                scan_type = "filesystem"

        # Build command
        cmd = ["trufflehog"]

        # Scan type
        if scan_type == "git":
            cmd.append("git")
        elif scan_type == "github":
            cmd.append("github")
        elif scan_type == "filesystem":
            cmd.append("filesystem")

        # Target
        cmd.append(target)

        # JSON output
        cmd.append("--json")

        # Verification (enabled by default)
        if options.get("verify", True):
            cmd.append("--verify")

        # Only verified (skip unverified)
        if options.get("only_verified", False):
            cmd.append("--only-verified")

        # Include specific detectors
        if options.get("include_detectors"):
            cmd.extend(["--include-detectors", options["include_detectors"]])

        # Exclude detectors
        if options.get("exclude_detectors"):
            cmd.extend(["--exclude-detectors", options["exclude_detectors"]])

        # Git-specific options
        if scan_type == "git":
            if options.get("since_commit"):
                cmd.extend(["--since-commit", options["since_commit"]])

            if options.get("max_depth"):
                cmd.extend(["--max-depth", str(options["max_depth"])])

        self.logger.info(f"Executing: {' '.join(cmd)}")

        try:
            # Execute command
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait with timeout (max 60 minutes for large repos)
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=3600
            )

            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            raw_output = stdout.decode()
            stderr_output = stderr.decode()

            # Parse findings
            findings = self.parse_output_to_findings(raw_output, target)

            # Categorize findings
            verified_count = sum(1 for f in findings if f.get("verified", False))
            unverified_count = len(findings) - verified_count

            # Group by detector type
            detector_counts = {}
            for finding in findings:
                detector = finding.get("detector_type", "unknown")
                detector_counts[detector] = detector_counts.get(detector, 0) + 1

            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                findings=findings,
                raw_output=raw_output,
                structured_output={
                    "total_secrets": len(findings),
                    "verified_secrets": verified_count,
                    "unverified_secrets": unverified_count,
                    "by_detector": detector_counts,
                    "target": target,
                    "scan_type": scan_type
                },
                command_executed=" ".join(cmd),
                exit_code=proc.returncode,
                warnings=[stderr_output] if stderr_output else []
            )

        except asyncio.TimeoutError:
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            self.logger.error("trufflehog scan timed out after 60 minutes")

            return ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
                error_message="Scan timeout after 60 minutes"
            )

        except Exception as e:
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            self.logger.error(f"trufflehog execution failed: {str(e)}")

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
        Parse trufflehog JSON output to findings

        TruffleHog v3+ outputs newline-delimited JSON
        """
        findings = []

        for line in raw_output.strip().split("\n"):
            if not line.strip():
                continue

            try:
                data = json.loads(line)

                # Extract source metadata
                source_metadata = data.get("SourceMetadata", {})
                data_field = source_metadata.get("Data", {})

                # Extract detector info
                detector_type = data.get("DetectorType", "unknown")
                detector_name = data.get("DetectorName", "unknown")

                # Verified status
                verified = data.get("Verified", False)

                # Raw secret (redacted)
                raw_secret = data.get("Raw", "")
                redacted_secret = self._redact_secret(raw_secret)

                finding = {
                    "type": "secret",
                    "detector_type": detector_type,
                    "detector_name": detector_name,
                    "verified": verified,
                    "secret_redacted": redacted_secret,
                    "file": data_field.get("file", ""),
                    "commit": data_field.get("commit", ""),
                    "email": data_field.get("email", ""),
                    "timestamp": data_field.get("timestamp", ""),
                    "line": data_field.get("line", 0),
                    "discovered_at": datetime.utcnow().isoformat(),
                    "target": target,
                    "severity": "critical" if verified else "high"
                }

                findings.append(finding)

            except json.JSONDecodeError:
                self.logger.warning(f"Failed to parse JSON line: {line[:100]}")
                continue

        self.logger.info(f"Parsed {len(findings)} secrets")
        return findings

    def _redact_secret(self, secret: str) -> str:
        """Redact secret for safe logging"""
        if len(secret) <= 8:
            return "***"

        # Show first 4 and last 4 characters
        return f"{secret[:4]}...{secret[-4:]}"
