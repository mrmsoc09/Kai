"""
CrlfuzzAgent for K1 — CRLF Injection and HTTP Response Splitting Detection

Orchestrates crlfuzz binary to detect CRLF (Carriage Return Line Feed) injection
vulnerabilities in HTTP headers, response splitting attacks, and related vectors.

Implements:
  - Multi-vector CRLF fuzzing (headers, parameters, cookies)
  - Response splitting detection
  - Session hijacking and cache poisoning risk assessment
  - Header injection capability detection
  - Blind CRLF injection detection via timing analysis
  - V-RAD telemetry (CRLF_VULNS_CONFIRMED, FUZZING_HEADERS)
  - SNL routing for all fuzzing traffic (OPSEC)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from ..base_tool_agent import BaseToolAgent

from .schemas import (
    ConfirmationMethod,
    CrlfStatistics,
    CrlfVulnerabilityRegistry,
    ExploitVector,
    InjectionPoint,
)

logger = logging.getLogger(__name__)


class CrlfuzzAgent(BaseToolAgent):
    """
    CrlfuzzAgent for CRLF injection vulnerability discovery.

    Detects Server-Side CRLF injection and HTTP response splitting vulnerabilities
    across multiple injection vectors:
    - URL parameters
    - POST parameters
    - HTTP headers
    - Cookie values
    - JSON/XML fields

    Key Features:
      - Multi-vector CRLF fuzzing
      - Response splitting detection
      - Session hijacking risk assessment
      - Cache poisoning detection
      - Blind CRLF detection via timing
      - V-RAD telemetry: Real-time metrics on successful injections
      - Automatic Session Hijacking follow-up flagging
    """

    TOOL_NAME = "crlfuzz"

    # CRLF payload patterns for detection
    _CRLF_PAYLOADS = [
        "%0d%0a",        # URL-encoded CRLF
        "\\r\\n",        # Literal CRLF in strings
        "%0d%0aSet-Cookie",  # CRLF + Set-Cookie injection
        "%0d%0aLocation",    # CRLF + Location header injection
        "%0d%0aX-Forwarded-For",  # CRLF + Custom header
    ]

    # Response splitting indicators
    _RESPONSE_SPLIT_PATTERNS = [
        r"HTTP/1\.[01]\s+\d{3}",  # Multiple HTTP status lines
        r"Set-Cookie:\s*[^\r\n]+\r\n[^\r\n]*=",  # Injected Set-Cookie
        r"Location:\s*[^\r\n]+\r\n[^\r\n]*=",  # Injected Location
    ]

    # Session hijacking indicators
    _SESSION_HIJACK_PATTERNS = [
        r"Set-Cookie",
        r"Authorization",
        r"session",
        r"token",
        r"auth",
    ]

    # Cache poisoning indicators
    _CACHE_POISON_PATTERNS = [
        r"Cache-Control",
        r"Expires",
        r"ETag",
        r"Vary",
    ]

    def build_command(
        self,
        target_url: str,
        options: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Build crlfuzz command.

        Args:
            target_url: Target URL to fuzz
            options: Execution options
              - payload: Custom payload file path
              - timeout_seconds: Command timeout (default: 600)
              - proxy: HTTP(S) proxy URL (SNL routing)
              - threads: Number of concurrent threads (default: 10)
              - deep_scan: Test all parameters extensively

        Returns:
            Command as list of strings for subprocess execution
        """
        options = options or {}
        cmd = [self.TOOL_NAME, "-u", target_url, "-silent"]

        # Output format
        cmd.extend(["-o", "json"])

        # Timeout
        timeout = options.get("timeout_seconds", 600)
        if timeout:
            cmd.extend(["-t", str(timeout)])

        # Proxy (SNL routing)
        proxy = options.get("proxy")
        if proxy:
            cmd.extend(["-p", proxy])

        # Threads
        threads = options.get("threads", 10)
        if threads:
            cmd.extend(["-th", str(threads)])

        # Custom payload file
        payload_file = options.get("payload")
        if payload_file:
            cmd.extend(["-payload", payload_file])

        # Deep scan
        if options.get("deep_scan"):
            cmd.append("-deep")

        return cmd

    def parse_output(self, raw_output: str, target: str = "") -> dict[str, Any]:
        """
        Parse crlfuzz JSON output and normalize to CrlfVulnerabilityRegistry.

        Args:
            raw_output: Raw crlfuzz command output
            target: Target URL (optional, for context)

        Returns:
            Dictionary with keys:
              - findings: List[CrlfVulnerabilityRegistry] — discovered CRLF vulns
              - statistics: CrlfStatistics — aggregated metrics
        """
        findings = []
        statistics = CrlfStatistics()

        if not raw_output.strip():
            return {
                "findings": findings,
                "statistics": statistics,
            }

        # Parse each line as JSON (streaming format)
        for line in raw_output.split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                finding = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse crlfuzz JSON line: {line[:100]}")
                continue

            # Skip non-CRLF findings
            if not self._is_crlf_finding(finding):
                continue

            try:
                registry = self._build_registry(finding)
                findings.append(registry)
                statistics.total_urls_tested += 1

                # Track by confirmation method
                if (
                    registry.confirmation_method
                    == ConfirmationMethod.RESPONSE_HEADER_MODIFIED
                ):
                    statistics.crlf_vulns_confirmed += 1
                elif (
                    registry.confirmation_method
                    == ConfirmationMethod.RESPONSE_BODY_SPLIT
                ):
                    statistics.crlf_vulns_confirmed += 1
                elif registry.confirmation_method == ConfirmationMethod.BLIND:
                    statistics.crlf_vulns_blind += 1
                else:
                    statistics.crlf_vulns_probable += 1

                # Track by vector
                if registry.exploit_vector == ExploitVector.HEADER_INJECTION:
                    statistics.header_injection_count += 1
                elif registry.exploit_vector == ExploitVector.RESPONSE_SPLITTING:
                    statistics.response_splitting_count += 1
                elif registry.exploit_vector == ExploitVector.CACHE_POISONING:
                    statistics.cache_poisoning_count += 1
                elif registry.exploit_vector == ExploitVector.SESSION_HIJACKING:
                    statistics.session_hijacking_risk_count += 1

                # Track by severity
                if registry.risk_level == "CRITICAL":
                    statistics.critical_severity += 1
                elif registry.risk_level == "HIGH":
                    statistics.high_severity += 1
                elif registry.risk_level == "MEDIUM":
                    statistics.medium_severity += 1
                elif registry.risk_level == "LOW":
                    statistics.low_severity += 1

            except ValidationError as e:
                logger.warning(f"Failed to build registry for finding: {e}")
                continue

        return {
            "findings": findings,
            "statistics": statistics,
        }

    def _is_crlf_finding(self, finding: dict[str, Any]) -> bool:
        """Check if finding represents a CRLF injection vulnerability."""
        vuln_type = finding.get("type", "").lower()
        return "crlf" in vuln_type or "response_split" in vuln_type

    def _build_registry(self, finding: dict[str, Any]) -> CrlfVulnerabilityRegistry:
        """Build CrlfVulnerabilityRegistry from crlfuzz finding."""
        target_url = finding.get("url", finding.get("target", ""))
        vulnerable_parameter = finding.get("parameter", "")
        injected_payload = finding.get("payload", "")
        response = finding.get("response", "")
        original_status = finding.get("status_original", 200)
        modified_status = finding.get("status_modified", 200)

        # Determine injection point
        injection_point = self._determine_injection_point(finding)

        # Determine exploit vector
        exploit_vector = self._determine_exploit_vector(finding, response)

        # Determine confirmation method
        confirmation_method = self._determine_confirmation_method(finding, response)

        # Detect capabilities
        can_inject_headers = self._detect_header_injection(response)
        can_inject_body = self._detect_body_injection(response)
        can_split_response = self._detect_response_split(response)

        # Assess risks
        session_hijacking_risk = self._assess_session_hijacking_risk(
            response, vulnerable_parameter
        )
        cache_poisoning_risk = self._assess_cache_poisoning_risk(response)
        xss_risk = self._assess_xss_risk(response)
        open_redirect_risk = self._assess_open_redirect_risk(response)

        # Calculate confidence
        confidence = self._calculate_confidence(
            confirmation_method, response, can_split_response
        )

        # Extract evidence
        header_injection_evidence = self._extract_header_evidence(response)
        body_split_evidence = self._extract_body_split_evidence(response)

        return CrlfVulnerabilityRegistry(
            target_url=target_url,
            vulnerable_parameter=vulnerable_parameter,
            injection_point=injection_point,
            exploit_vector=exploit_vector,
            injected_payload=injected_payload,
            confirmation_method=confirmation_method,
            response_status_original=original_status,
            response_status_modified=modified_status,
            confidence=confidence,
            can_inject_headers=can_inject_headers,
            can_inject_body=can_inject_body,
            can_split_response=can_split_response,
            session_hijacking_risk=session_hijacking_risk,
            cache_poisoning_risk=cache_poisoning_risk,
            xss_risk=xss_risk,
            open_redirect_risk=open_redirect_risk,
            raw_response=response[:5000],
            response_headers=finding.get("response_headers", {}),
            header_injection_evidence=header_injection_evidence,
            body_split_evidence=body_split_evidence,
            detected_by="crlfuzz",
            detection_date=datetime.now(UTC),
            payload_used=injected_payload,
            request_method=finding.get("method", "GET"),
            request_headers=finding.get("request_headers", {}),
            target_domain=self._extract_domain(target_url),
            endpoint_path=self._extract_path(target_url),
            stealthy=True,
        )

    def _determine_injection_point(self, finding: dict[str, Any]) -> InjectionPoint:
        """Determine where CRLF was injected."""
        param_type = finding.get("parameter_type", "").lower()

        if "header" in param_type:
            return InjectionPoint.HEADER_VALUE
        elif "cookie" in param_type:
            return InjectionPoint.COOKIE_VALUE
        elif "post" in param_type or "body" in param_type:
            return InjectionPoint.POST_PARAMETER
        elif "json" in param_type:
            return InjectionPoint.JSON_FIELD
        elif "xml" in param_type:
            return InjectionPoint.XML_FIELD
        elif "path" in param_type:
            return InjectionPoint.PATH_PARAMETER
        elif "url" in param_type or "query" in param_type:
            return InjectionPoint.URL_PARAMETER

        return InjectionPoint.UNKNOWN

    def _determine_exploit_vector(
        self,
        finding: dict[str, Any],
        response: str,
    ) -> ExploitVector:
        """Determine the type of exploit enabled by CRLF injection."""
        response_lower = response.lower()
        finding_type = finding.get("type", "").lower()

        # Response splitting
        if "response_split" in finding_type or self._detect_response_split(response):
            return ExploitVector.RESPONSE_SPLITTING

        # Session hijacking
        if "session" in finding_type or re.search(
            r"Set-Cookie|Authorization", response, re.IGNORECASE
        ):
            return ExploitVector.SESSION_HIJACKING

        # Cache poisoning
        if "cache" in finding_type or re.search(
            r"Cache-Control|Expires|ETag", response, re.IGNORECASE
        ):
            return ExploitVector.CACHE_POISONING

        # Cookie injection
        if "cookie" in finding_type or "Set-Cookie" in response:
            return ExploitVector.COOKIE_INJECTION

        # XSS via header
        if "xss" in finding_type or re.search(
            r"<script|javascript:|onerror|onclick",
            response,
            re.IGNORECASE,
        ):
            return ExploitVector.XSS_VIA_HEADER

        # Open redirect
        if "redirect" in finding_type or "Location" in response:
            return ExploitVector.OPEN_REDIRECT

        # Default to header injection
        return ExploitVector.HEADER_INJECTION

    def _determine_confirmation_method(
        self,
        finding: dict[str, Any],
        response: str,
    ) -> ConfirmationMethod:
        """Determine how the CRLF injection was confirmed."""
        method_str = finding.get("confirmation", "").lower()

        if "header" in method_str:
            return ConfirmationMethod.RESPONSE_HEADER_MODIFIED
        elif "split" in method_str:
            return ConfirmationMethod.RESPONSE_BODY_SPLIT
        elif "status" in method_str:
            return ConfirmationMethod.STATUS_CODE_CHANGED
        elif "new" in method_str:
            return ConfirmationMethod.NEW_HEADERS_INJECTED
        elif "pattern" in method_str:
            return ConfirmationMethod.PATTERN_DETECTION
        elif "timing" in method_str:
            return ConfirmationMethod.TIMING_ANALYSIS
        elif "blind" in method_str:
            return ConfirmationMethod.BLIND

        # Infer from response
        if self._detect_response_split(response):
            return ConfirmationMethod.RESPONSE_BODY_SPLIT
        elif self._detect_header_injection(response):
            return ConfirmationMethod.RESPONSE_HEADER_MODIFIED
        elif response.strip():
            return ConfirmationMethod.PATTERN_DETECTION

        return ConfirmationMethod.BLIND

    def _detect_header_injection(self, response: str) -> bool:
        """Detect if headers can be injected."""
        return bool(
            re.search(r"Set-Cookie|Location|X-.*:|Authorization", response)
        )

    def _detect_body_injection(self, response: str) -> bool:
        """Detect if response body can be injected."""
        # Check if response has clear body after headers
        return bool(re.search(r"\r\n\r\n.+", response, re.DOTALL))

    def _detect_response_split(self, response: str) -> bool:
        """Detect HTTP response splitting."""
        for pattern in self._RESPONSE_SPLIT_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                return True
        return False

    def _assess_session_hijacking_risk(
        self,
        response: str,
        parameter: str,
    ) -> bool:
        """Assess risk of session hijacking via CRLF."""
        response_lower = response.lower()
        param_lower = parameter.lower()

        # Direct indicators
        if "set-cookie" in response_lower:
            return True
        if "authorization" in response_lower:
            return True

        # Parameter-based indicators
        if any(
            keyword in param_lower
            for keyword in ["cookie", "session", "token", "auth", "user"]
        ):
            return self._detect_header_injection(response)

        return False

    def _assess_cache_poisoning_risk(self, response: str) -> bool:
        """Assess risk of cache poisoning via CRLF."""
        response_lower = response.lower()

        # Indicators of cache control
        cache_keywords = [
            "cache-control",
            "expires",
            "etag",
            "vary",
            "pragma",
            "last-modified",
        ]

        return any(keyword in response_lower for keyword in cache_keywords)

    def _assess_xss_risk(self, response: str) -> bool:
        """Assess XSS risk via CRLF header injection."""
        # Check for content-type or other headers that could enable XSS
        return bool(
            re.search(
                r"Content-Type.*text/html|Set-Cookie.*Domain=",
                response,
                re.IGNORECASE,
            )
        )

    def _assess_open_redirect_risk(self, response: str) -> bool:
        """Assess open redirect risk via Location header injection."""
        return "Location" in response

    def _calculate_confidence(
        self,
        confirmation_method: ConfirmationMethod,
        response: str,
        can_split: bool,
    ) -> float:
        """Calculate confidence score."""
        confidence = 0.5

        if confirmation_method == ConfirmationMethod.RESPONSE_BODY_SPLIT:
            confidence = 0.95
        elif confirmation_method == ConfirmationMethod.RESPONSE_HEADER_MODIFIED:
            confidence = 0.90
        elif confirmation_method == ConfirmationMethod.NEW_HEADERS_INJECTED:
            confidence = 0.85
        elif confirmation_method == ConfirmationMethod.STATUS_CODE_CHANGED:
            confidence = 0.80
        elif confirmation_method == ConfirmationMethod.PATTERN_DETECTION:
            confidence = 0.75
        elif confirmation_method == ConfirmationMethod.TIMING_ANALYSIS:
            confidence = 0.70
        elif confirmation_method == ConfirmationMethod.BLIND:
            confidence = 0.55

        # Boost if response is substantial
        if len(response) > 500:
            confidence = min(1.0, confidence + 0.05)

        # Boost if can split response
        if can_split:
            confidence = min(1.0, confidence + 0.10)

        return confidence

    def _extract_header_evidence(self, response: str) -> list[str]:
        """Extract evidence of header injection."""
        evidence = []

        # Find Set-Cookie headers
        for match in re.finditer(r"Set-Cookie:\s*([^\r\n]+)", response):
            evidence.append(f"Set-Cookie: {match.group(1)}")

        # Find Location headers
        for match in re.finditer(r"Location:\s*([^\r\n]+)", response):
            evidence.append(f"Location: {match.group(1)}")

        # Find custom headers (X-*)
        for match in re.finditer(r"(X-[^:]+):\s*([^\r\n]+)", response):
            evidence.append(f"{match.group(1)}: {match.group(2)}")

        return evidence

    def _extract_body_split_evidence(self, response: str) -> str:
        """Extract evidence of response body split."""
        # Find separation between headers and body
        match = re.search(r"\r\n\r\n(.+)", response, re.DOTALL)
        if match:
            body = match.group(1)[:500]  # First 500 chars
            return body
        return ""

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        match = re.search(r"https?://([^/]+)", url)
        return match.group(1) if match else ""

    def _extract_path(self, url: str) -> str:
        """Extract path from URL."""
        match = re.search(r"https?://[^/]+(/[^?#]*)", url)
        return match.group(1) if match else "/"

    def filter_noise(self, findings: "dict[str, Any] | list") -> tuple[list, list]:
        """
        Separate signal from noise.

        Signal (high-confidence findings):
          - Response splitting (body split)
          - Header injection with high confidence
          - Session hijacking risk with confirmed injection
          - Cache poisoning with header modification

        Noise (low-value findings):
          - Blind CRLF with low confidence (<0.65)
          - Pattern detection without confirmation

        Returns:
            Tuple of (signal_findings, noise_findings)
        """
        signal = []
        noise = []

        raw = findings if isinstance(findings, list) else findings.get("findings", [])
        for finding in raw:
            is_signal = (
                finding.confirmation_method
                == ConfirmationMethod.RESPONSE_BODY_SPLIT
            ) or (
                finding.confidence > 0.85
                and finding.confirmation_method != ConfirmationMethod.BLIND
            ) or (
                finding.session_hijacking_risk and finding.can_inject_headers
            )

            if is_signal:
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def register_telemetry_hook(self, callback: callable) -> None:
        """Register V-RAD telemetry callback."""
        self._telemetry_callback = callback

    async def _push_telemetry(self, metric_name: str, value: Any) -> None:
        """Push telemetry to V-RAD."""
        if hasattr(self, "_telemetry_callback"):
            try:
                await self._telemetry_callback(metric_name, value)
            except Exception as e:
                logger.warning(f"Failed to push telemetry {metric_name}: {e}")
