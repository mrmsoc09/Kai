"""
Evidence capture orchestrator for playbook execution.
Automatically captures HTTP requests/responses, screenshots, and curl commands.
Integrates with Vault for secure evidence storage.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CapturedEvidence:
    """Single piece of captured evidence."""

    evidence_type: str  # "http_request", "screenshot", "curl_command", "log"
    target: str
    cve_id: str
    timestamp: str
    content: Dict[str, Any] | str
    severity: str = "high"
    description: str = ""
    sha256_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA256 hash of evidence content."""
        import json

        if isinstance(self.content, dict):
            content_str = json.dumps(self.content, sort_keys=True)
        else:
            content_str = str(self.content)

        self.sha256_hash = hashlib.sha256(
            content_str.encode()
        ).hexdigest()
        return self.sha256_hash

    def to_vault_payload(self) -> Dict[str, Any]:
        """Convert evidence to Vault storage payload."""
        return {
            "evidence_type": self.evidence_type,
            "target": self.target,
            "cve_id": self.cve_id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "description": self.description,
            "sha256_hash": self.sha256_hash or self.compute_hash(),
            "content": self.content,
        }


class EvidenceCapturer:
    """
    Captures evidence during playbook execution.
    Hooks into HTTP traffic, screenshots, command output.
    """

    def __init__(self, vault_client=None):
        """
        Initialize evidence capturer.

        Args:
            vault_client: Optional VaultClient for storing evidence
        """
        self.vault_client = vault_client
        self.captured_evidence: list[CapturedEvidence] = []

    async def capture_http_evidence(
        self,
        target: str,
        cve_id: str,
        method: str,
        url: str,
        request_headers: Dict[str, str],
        request_body: Optional[str],
        response_status: int,
        response_headers: Dict[str, str],
        response_body: Optional[str],
        description: str = "",
    ) -> CapturedEvidence:
        """
        Capture HTTP request/response pair as evidence.

        Args:
            target: Target URL
            cve_id: Associated CVE ID
            method: HTTP method
            url: Request URL
            request_headers: Request headers dict
            request_body: Request body (optional)
            response_status: HTTP response status code
            response_headers: Response headers dict
            response_body: Response body (optional, capped at 10KB)
            description: Description of evidence

        Returns:
            CapturedEvidence object
        """
        # Cap response body to prevent vault size issues
        response_body_capped = (
            response_body[:10240] if response_body else None
        )

        evidence = CapturedEvidence(
            evidence_type="http_request_response",
            target=target,
            cve_id=cve_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description
            or f"{method} {url} → {response_status}",
            severity="high",
            content={
                "request": {
                    "method": method,
                    "url": url,
                    "headers": request_headers,
                    "body": request_body,
                },
                "response": {
                    "status": response_status,
                    "headers": response_headers,
                    "body": response_body_capped,
                },
            },
        )

        evidence.compute_hash()
        self.captured_evidence.append(evidence)

        # Store in Vault if client available
        if self.vault_client:
            await self._vault_store_http_evidence(evidence)

        logger.info(
            f"Captured HTTP evidence for {cve_id} on {target}: "
            f"{evidence.sha256_hash[:8]}"
        )
        return evidence

    async def capture_curl_command(
        self,
        target: str,
        cve_id: str,
        curl_command: str,
        description: str = "",
    ) -> CapturedEvidence:
        """
        Capture curl command for reproducing vulnerability.

        Args:
            target: Target URL
            cve_id: Associated CVE ID
            curl_command: Complete curl command (credentials redacted)
            description: Description of what command does

        Returns:
            CapturedEvidence object
        """
        evidence = CapturedEvidence(
            evidence_type="curl_command",
            target=target,
            cve_id=cve_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description or "Reproducible curl command",
            severity="high",
            content={"curl_command": curl_command},
        )

        evidence.compute_hash()
        self.captured_evidence.append(evidence)

        # Store in Vault if client available
        if self.vault_client:
            await self._vault_store_curl_evidence(evidence)

        logger.info(
            f"Captured curl evidence for {cve_id} on {target}: "
            f"{evidence.sha256_hash[:8]}"
        )
        return evidence

    async def capture_screenshot(
        self,
        target: str,
        cve_id: str,
        screenshot_base64: str,
        description: str = "",
    ) -> CapturedEvidence:
        """
        Capture screenshot evidence (base64 encoded).

        Args:
            target: Target URL
            cve_id: Associated CVE ID
            screenshot_base64: Base64-encoded PNG/JPEG
            description: What screenshot shows

        Returns:
            CapturedEvidence object
        """
        # Decode to verify validity and get size
        try:
            screenshot_bytes = base64.b64decode(screenshot_base64)
            screenshot_size_kb = len(screenshot_bytes) / 1024
        except Exception as e:
            logger.error(f"Invalid base64 screenshot: {str(e)}")
            raise

        # Cap at 5MB
        if screenshot_size_kb > 5120:
            logger.warning(
                f"Screenshot too large ({screenshot_size_kb:.1f} KB), "
                "truncating"
            )
            screenshot_bytes = screenshot_bytes[:5242880]
            screenshot_base64 = base64.b64encode(
                screenshot_bytes
            ).decode()

        evidence = CapturedEvidence(
            evidence_type="screenshot",
            target=target,
            cve_id=cve_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description or "Screenshot evidence",
            severity="high",
            content={
                "screenshot_base64": screenshot_base64,
                "size_bytes": len(screenshot_bytes),
            },
        )

        evidence.compute_hash()
        self.captured_evidence.append(evidence)

        # Store in Vault if client available
        if self.vault_client:
            await self._vault_store_screenshot_evidence(evidence)

        logger.info(
            f"Captured screenshot for {cve_id} on {target}: "
            f"{screenshot_size_kb:.1f} KB, {evidence.sha256_hash[:8]}"
        )
        return evidence

    async def capture_tool_output(
        self,
        target: str,
        cve_id: str,
        tool_name: str,
        output: str,
        description: str = "",
    ) -> CapturedEvidence:
        """
        Capture output from exploitation tool as evidence.

        Args:
            target: Target URL
            cve_id: Associated CVE ID
            tool_name: Name of tool that produced output
            output: Tool output (capped at 50KB)
            description: Description of evidence

        Returns:
            CapturedEvidence object
        """
        # Cap output to prevent vault issues
        output_capped = output[:51200] if output else ""

        evidence = CapturedEvidence(
            evidence_type="tool_output",
            target=target,
            cve_id=cve_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            description=description or f"Output from {tool_name}",
            severity="high",
            content={"tool_name": tool_name, "output": output_capped},
        )

        evidence.compute_hash()
        self.captured_evidence.append(evidence)

        # Store in Vault if client available
        if self.vault_client:
            await self._vault_store_tool_output(evidence)

        logger.info(
            f"Captured {tool_name} output for {cve_id}: "
            f"{evidence.sha256_hash[:8]}"
        )
        return evidence

    async def _vault_store_http_evidence(
        self, evidence: CapturedEvidence
    ) -> Optional[str]:
        """Store HTTP evidence in Vault."""
        if not self.vault_client:
            return None

        try:
            path = (
                f"secret/data/evidence/{evidence.target}/"
                f"{evidence.cve_id}/http/{evidence.timestamp.replace(':', '-')}"
            )
            await self.vault_client.write_secret(
                path, evidence.to_vault_payload()
            )
            logger.debug(f"Stored evidence in Vault at {path}")
            return path
        except Exception as e:
            logger.error(f"Error storing evidence in Vault: {str(e)}")
            return None

    async def _vault_store_curl_evidence(
        self, evidence: CapturedEvidence
    ) -> Optional[str]:
        """Store curl command evidence in Vault."""
        if not self.vault_client:
            return None

        try:
            path = (
                f"secret/data/evidence/{evidence.target}/"
                f"{evidence.cve_id}/curl_repro/{evidence.timestamp.replace(':', '-')}"
            )
            await self.vault_client.write_secret(
                path, evidence.to_vault_payload()
            )
            logger.debug(f"Stored curl evidence in Vault at {path}")
            return path
        except Exception as e:
            logger.error(f"Error storing curl evidence in Vault: {str(e)}")
            return None

    async def _vault_store_screenshot_evidence(
        self, evidence: CapturedEvidence
    ) -> Optional[str]:
        """Store screenshot evidence in Vault."""
        if not self.vault_client:
            return None

        try:
            path = (
                f"secret/data/evidence/{evidence.target}/"
                f"{evidence.cve_id}/screenshots/{evidence.timestamp.replace(':', '-')}"
            )
            await self.vault_client.write_secret(
                path, evidence.to_vault_payload()
            )
            logger.debug(f"Stored screenshot in Vault at {path}")
            return path
        except Exception as e:
            logger.error(f"Error storing screenshot in Vault: {str(e)}")
            return None

    async def _vault_store_tool_output(
        self, evidence: CapturedEvidence
    ) -> Optional[str]:
        """Store tool output evidence in Vault."""
        if not self.vault_client:
            return None

        try:
            path = (
                f"secret/data/evidence/{evidence.target}/"
                f"{evidence.cve_id}/tool_output/{evidence.timestamp.replace(':', '-')}"
            )
            await self.vault_client.write_secret(
                path, evidence.to_vault_payload()
            )
            logger.debug(f"Stored tool output in Vault at {path}")
            return path
        except Exception as e:
            logger.error(f"Error storing tool output in Vault: {str(e)}")
            return None

    def get_evidence_summary(
        self, cve_id: str, target: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get summary of captured evidence.

        Args:
            cve_id: CVE ID to filter by
            target: Optional target URL to filter by

        Returns:
            Summary dict with evidence counts and types
        """
        filtered = [
            e
            for e in self.captured_evidence
            if e.cve_id == cve_id
            and (not target or e.target == target)
        ]

        by_type = {}
        for evidence in filtered:
            by_type[evidence.evidence_type] = (
                by_type.get(evidence.evidence_type, 0) + 1
            )

        return {
            "cve_id": cve_id,
            "target": target,
            "total_evidence": len(filtered),
            "by_type": by_type,
            "evidence_hashes": [e.sha256_hash for e in filtered],
        }

    def clear_evidence(self) -> None:
        """Clear captured evidence from memory."""
        self.captured_evidence.clear()
        logger.info("Cleared captured evidence from memory")
