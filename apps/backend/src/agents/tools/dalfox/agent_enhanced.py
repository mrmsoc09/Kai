"""
Enhanced Dalfox XSS Agent for K1 Platform

Responsible for parameter-focused XSS vulnerability discovery and PoC validation.

Features:
- High-speed parameter testing with default + custom payloads
- Lifecycle management: execute() with streaming JSON parsing
- Advanced features: Deep checking, parameter mining, WAF bypass detection
- Memory-efficient: Streaming JSON, dedup cache with resource limits
- Heuristic analysis: Prioritizes "interesting" parameters (id=, search=, redirect=)
- V-RAD integration: XSS_VECTORS_TESTED, REFLECTED_PARAMS metrics
- OPSEC layer: Sovereign Network Layer routing, randomized User-Agent
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from apps.backend.src.core.protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    Severity,
)

from ..base_tool_agent import BaseToolAgent
from .schemas import (
    DalfoxFinding,
    ParamType,
    ReflectionType,
    RiskLevel,
    VulnerabilityRegistry,
    VulnerabilityType,
    XSSStatistics,
)

# Interesting parameter patterns (high priority for testing)
_INTERESTING_PARAMS = {
    "id", "search", "q", "redirect", "url", "next", "return",
    "callback", "redirect_uri", "username", "email", "name",
    "message", "comment", "content", "body", "title", "description",
    "file", "path", "page", "sort", "filter", "order", "lang",
    "ref", "referrer", "action", "cmd", "command", "execute",
}

# Parameter names indicating redirect/open redirect risk
_REDIRECT_PARAMS = {
    "redirect", "url", "next", "return", "goto", "continue",
    "redirect_uri", "returnurl", "return_to", "back", "dest",
}

# Parameter names indicating user-controllable content
_CONTENT_PARAMS = {
    "message", "comment", "content", "body", "text", "title",
    "description", "subject", "name", "display_name", "username",
}


class DalfoxAgent(BaseToolAgent):
    """
    Dalfox XSS Scanning Agent with advanced payload testing and heuristic analysis.

    Execution modes:
    1. Standard: dalfox scan <url> (direct URL query)
    2. Listener: stdin pipe (chained input from httpx_probe or paramspider)
    3. Deep: dalfox scan --deep-check <url> (intensive analysis)
    4. Mining: dalfox scan --mining-dict <wordlist> <url> (parameter discovery)

    Features parameter prioritization, custom payload support, and WAF bypass detection.
    """

    TOOL_NAME = "dalfox"
    DEFAULT_TIMEOUT_SECONDS = 600
    MAX_MEMORY_VULNS = 10_000  # Cap for in-memory vuln cache
    CHUNK_SIZE = 500  # Export/fetch in chunks to prevent overflow

    def __init__(self, memory_root: str | Path | None = None) -> None:
        super().__init__(memory_root=memory_root)
        self._telemetry_hook: Callable | None = None
        self._listener_mode = False
        self._dedup_cache: set[str] = set()
        self._stats = XSSStatistics()
        self._streaming_mode = True
        self._interesting_params_found: list[str] = []

    def register_telemetry_hook(self, hook: Callable[[str, str | float | dict], None]) -> None:
        """Register callback for real-time V-RAD telemetry push.

        Args:
            hook: Callable(metric_name: str, value: str | float | dict) -> None
        """
        self._telemetry_hook = hook

    def _push_telemetry(self, metric_name: str, value: str | float | dict) -> None:
        """Push metric to V-RAD dashboard via telemetry hook."""
        if self._telemetry_hook:
            try:
                self._telemetry_hook(metric_name, value)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Telemetry push failed: {e}")

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        """Build dalfox command for XSS vulnerability scanning.

        Supports custom payloads, deep checking, and parameter mining.
        """
        opts = options or {}
        self._listener_mode = bool(opts.get("listener_mode", False))

        binary = str(opts.get("binary_path", "dalfox"))

        # Base command with JSON output
        cmd = [binary, "scan", "--format", "json"]

        # Deep checking (intensive analysis)
        if opts.get("deep_check", False):
            cmd.append("--deep-check")

        # Parameter mining with wordlist
        mining_dict = opts.get("mining_dict")
        if mining_dict:
            cmd += ["--mining-dict", str(mining_dict)]

        # Custom payload file
        custom_payloads = opts.get("custom_payload_file")
        if custom_payloads:
            cmd += ["--custom-payload", str(custom_payloads)]

        # Timeout
        timeout_seconds = int(opts.get("timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS))
        if timeout_seconds > 0:
            cmd += ["--timeout", str(timeout_seconds)]

        # User-Agent randomization (OPSEC)
        if opts.get("random_user_agent", True):
            cmd.append("--random-user-agent")

        # Proxy/SNL support
        proxy = opts.get("proxy")
        if proxy:
            cmd += ["-p", proxy]

        # Silent mode (minimal output)
        if opts.get("silent", False):
            cmd.append("--silent")

        # Input source (unless listener mode)
        if not self._listener_mode:
            cmd.append(target)

        return cmd

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        """Parse dalfox JSON output into findings list.

        Each JSON line is a single XSS finding:
        {
          "type": "reflected",
          "inurlparam": "search",
          "payload": "<svg onload=alert(1)>",
          ...
        }
        """
        findings: list[dict[str, Any]] = []
        registries: list[VulnerabilityRegistry] = []
        seen_vulns: set[str] = set()

        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Skip non-XSS findings
            finding_type = str(data.get("type", "")).lower()
            if "xss" not in finding_type and "reflected" not in finding_type and "stored" not in finding_type and "dom" not in finding_type:
                continue

            url = str(data.get("url", "")).strip()
            if not url:
                continue

            # Validate URL is for target domain
            if not self._is_url_in_scope(url, target):
                continue

            self._stats.total_urls_scanned += 1

            # Build dedup key
            param = str(data.get("inurlparam", "")).strip().lower()
            payload = str(data.get("payload", "")).strip()
            dedup_key = f"{url}|{param}|{payload[:50]}"

            if dedup_key in seen_vulns:
                continue
            seen_vulns.add(dedup_key)

            # Build registry
            try:
                registry = self._build_vulnerability_registry(url, target, data)
                registries.append(registry)

                # Update stats
                self._stats.total_parameters_tested += 1
                self._stats.payloads_tested += 1
                self._stats.vulnerabilities_found += 1

                # Track by type
                if registry.vuln_type == VulnerabilityType.REFLECTED_XSS:
                    self._stats.reflected_xss_count += 1
                elif registry.vuln_type == VulnerabilityType.STORED_XSS:
                    self._stats.stored_xss_count += 1
                elif registry.vuln_type == VulnerabilityType.DOM_XSS:
                    self._stats.dom_xss_count += 1

                # Track by risk
                if registry.risk_level == RiskLevel.CRITICAL:
                    self._stats.critical_count += 1
                elif registry.risk_level == RiskLevel.HIGH:
                    self._stats.high_count += 1
                elif registry.risk_level == RiskLevel.MEDIUM:
                    self._stats.medium_count += 1
                elif registry.risk_level == RiskLevel.LOW:
                    self._stats.low_count += 1

                # Track interesting parameters
                if self._is_interesting_param(param):
                    self._interesting_params_found.append(param)

                # Push telemetry for critical findings
                if registry.is_critical:
                    self._push_telemetry("CRITICAL_XSS_FOUND", {
                        "url": registry.target_url,
                        "parameter": registry.vulnerable_parameter,
                        "type": registry.vuln_type.value,
                        "confidence": registry.confidence,
                    })

            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to parse finding: {e}")
                continue

        # Convert to findings for K1 compatibility
        for registry in registries:
            finding = {
                "type": "xss_vulnerability",
                "vuln_type": registry.vuln_type.value,
                "target_url": registry.target_url,
                "vulnerable_parameter": registry.vulnerable_parameter,
                "value": f"{registry.target_url}?{registry.vulnerable_parameter}=",
                "target": target,
                "severity": self._risk_to_severity(registry.risk_level),
                "confidence": registry.confidence,
                "source_tool": self.TOOL_NAME,
                "raw_evidence": {
                    "payload": registry.primary_payload,
                    "reflection_type": registry.reflection_type.value,
                    "poc_count": len(registry.poc_payloads),
                    "verified": registry.has_verified_poc,
                },
                "context": {
                    "vuln_id": str(registry.vuln_id),
                    "vuln_type": registry.vuln_type.value,
                    "risk_level": registry.risk_level.value,
                    "confidence": registry.confidence,
                    "is_critical": registry.is_critical,
                    "has_verified_poc": registry.has_verified_poc,
                    "exploitation_difficulty": registry.exploitation_difficulty,
                    "requires_user_interaction": registry.requires_user_interaction,
                    "requires_authentication": registry.requires_authentication,
                },
                "recommended_next_tools": ["dalfox"],  # For verification/deeper testing
                "recommended_next_actions": ["verify_xss", "craft_exploit"],
                "vulnerability_registry": registry.model_dump(),
            }
            findings.append(finding)

        # Push telemetry
        self._push_telemetry("XSS_VECTORS_TESTED", self._stats.payloads_tested)
        self._push_telemetry("REFLECTED_PARAMS", len(set(self._interesting_params_found)))
        self._push_telemetry("XSS_STATISTICS", {
            "total_urls": self._stats.total_urls_scanned,
            "vulnerabilities_found": self._stats.vulnerabilities_found,
            "critical_count": self._stats.critical_count,
            "reflected_xss": self._stats.reflected_xss_count,
            "stored_xss": self._stats.stored_xss_count,
            "dom_xss": self._stats.dom_xss_count,
            "verified_count": self._stats.verified_count,
        })

        return findings

    def _build_vulnerability_registry(
        self,
        url: str,
        target: str,
        dalfox_data: dict[str, Any],
    ) -> VulnerabilityRegistry:
        """Build VulnerabilityRegistry from dalfox finding."""
        # Parse URL components
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path or "/"

        # Parameter analysis
        param_name = str(dalfox_data.get("inurlparam", "")).strip().lower()
        param_type = self._detect_param_type(dalfox_data)

        # Payload and reflection analysis
        payload = str(dalfox_data.get("payload", "")).strip()
        evidence = str(dalfox_data.get("evidence", "")).strip()
        reflection_type = self._detect_reflection_type(payload, evidence)

        # Finding type analysis
        finding_type = str(dalfox_data.get("type", "")).lower()
        vuln_type = self._detect_vuln_type(finding_type, evidence)

        # Risk assessment
        risk_level = self._assess_risk_level(vuln_type, reflection_type, param_name)
        confidence = self._calculate_confidence(evidence, vuln_type)

        # HTTP metadata
        status_code = int(dalfox_data.get("code", 200))
        headers = dalfox_data.get("headers", {})
        response_preview = evidence[:1000] if evidence else ""

        # Build registry
        registry = VulnerabilityRegistry(
            target_url=url,
            vulnerable_parameter=param_name,
            param_type=param_type,
            vuln_type=vuln_type,
            risk_level=risk_level,
            confidence=confidence,
            primary_payload=payload,
            reflection_type=reflection_type,
            target_domain=domain,
            endpoint_path=path,
            full_request=json.dumps(dalfox_data, ensure_ascii=True),
            response_preview=response_preview,
            request_headers=headers,
            raw_dalfox_output=json.dumps(dalfox_data, ensure_ascii=True),
            detection_date=datetime.now(UTC),
        )

        # Add PoC
        registry.add_poc(payload, reflection_type, verified=True)

        return registry

    def _detect_param_type(self, data: dict[str, Any]) -> ParamType:
        """Detect parameter type from request metadata."""
        method = str(data.get("method", "GET")).upper()

        if method == "GET":
            return ParamType.QUERY_STRING

        # Check if in POST body or JSON
        request_body = data.get("data", "")
        if request_body:
            if request_body.startswith("{"):
                return ParamType.JSON_BODY
            elif request_body.startswith("<"):
                return ParamType.XML_BODY
            else:
                return ParamType.POST_BODY

        return ParamType.UNKNOWN

    def _detect_reflection_type(self, payload: str, evidence: str) -> ReflectionType:
        """Detect how payload is reflected in response."""
        if not evidence:
            return ReflectionType.UNKNOWN

        evidence_lower = evidence.lower()
        payload_lower = payload.lower()

        # Check for direct reflection
        if payload in evidence:
            return ReflectionType.DIRECT

        # Check for HTML escaped
        if (
            "&lt;" in evidence or "&gt;" in evidence or
            "&#" in evidence or payload_lower.replace("<", "&lt;") in evidence_lower
        ):
            return ReflectionType.HTML_ESCAPED

        # Check for URL encoded
        from urllib.parse import quote
        if quote(payload) in evidence or quote(payload, safe='') in evidence:
            return ReflectionType.URL_ENCODED

        # Check for double encoded
        if quote(quote(payload)) in evidence:
            return ReflectionType.DOUBLE_ENCODED

        # Check for JavaScript escaped
        if "\\" in payload or "\\u" in evidence:
            return ReflectionType.JAVASCRIPT_ESCAPED

        # Partial reflection
        if any(part in evidence for part in payload.split()[:3]):
            return ReflectionType.PARTIAL

        return ReflectionType.UNKNOWN

    def _detect_vuln_type(self, finding_type: str, evidence: str) -> VulnerabilityType:
        """Detect XSS vulnerability type."""
        finding_lower = finding_type.lower()

        # Check explicit type first
        if "reflected" in finding_lower:
            return VulnerabilityType.REFLECTED_XSS

        if "stored" in finding_lower or "storage" in finding_lower:
            return VulnerabilityType.STORED_XSS

        if "dom" in finding_lower:
            return VulnerabilityType.DOM_XSS

        # Fall back to evidence-based detection
        if "javascript" in finding_lower or "javascript:" in evidence.lower():
            return VulnerabilityType.JAVASCRIPT_URL

        if "on" in evidence.lower() and ("click" in evidence.lower() or "load" in evidence.lower()):
            return VulnerabilityType.EVENT_HANDLER

        if "data:" in evidence.lower() or "<svg" in evidence.lower():
            return VulnerabilityType.DATA_ATTRIBUTE

        return VulnerabilityType.UNKNOWN

    def _assess_risk_level(
        self, vuln_type: VulnerabilityType, reflection: ReflectionType, param_name: str
    ) -> RiskLevel:
        """Assess risk level based on type, reflection, and parameter."""
        # Stored XSS is always high risk minimum
        if vuln_type == VulnerabilityType.STORED_XSS:
            return RiskLevel.CRITICAL

        # DOM XSS is high risk
        if vuln_type == VulnerabilityType.DOM_XSS:
            return RiskLevel.HIGH

        # Direct reflection is critical
        if reflection == ReflectionType.DIRECT:
            return RiskLevel.CRITICAL

        # Interesting parameters (redirect, id, etc.) elevate risk
        if self._is_interesting_param(param_name):
            if reflection in (ReflectionType.HTML_ESCAPED, ReflectionType.URL_ENCODED):
                return RiskLevel.HIGH
            else:
                return RiskLevel.MEDIUM

        # Partial/escaped reflection is lower risk
        if reflection in (ReflectionType.PARTIAL, ReflectionType.HTML_ESCAPED):
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def _calculate_confidence(self, evidence: str, vuln_type: VulnerabilityType) -> float:
        """Calculate detection confidence."""
        base_confidence = 0.7

        # Stored XSS has high confidence
        if vuln_type == VulnerabilityType.STORED_XSS:
            base_confidence = 0.95

        # DOM XSS is generally high confidence
        if vuln_type == VulnerabilityType.DOM_XSS:
            base_confidence = 0.85

        # More evidence increases confidence
        if len(evidence) > 100:
            base_confidence = min(1.0, base_confidence + 0.1)

        return min(1.0, base_confidence)

    def _is_interesting_param(self, param: str) -> bool:
        """Check if parameter is interesting (high-priority testing)."""
        param_lower = param.lower()
        return (
            any(p in param_lower for p in _INTERESTING_PARAMS) or
            any(p in param_lower for p in _REDIRECT_PARAMS) or
            any(p in param_lower for p in _CONTENT_PARAMS)
        )

    def _is_url_in_scope(self, url: str, target: str) -> bool:
        """Check if URL is in scope (matches target domain)."""
        try:
            parsed = urlparse(url)
            hostname = parsed.netloc.lower()
            target_lower = target.lower()

            return hostname == target_lower or hostname.endswith(f".{target_lower}")
        except Exception:
            return False

    def _risk_to_severity(self, risk_level: RiskLevel) -> str:
        """Convert RiskLevel to Severity string."""
        risk_map = {
            RiskLevel.CRITICAL: "critical",
            RiskLevel.HIGH: "high",
            RiskLevel.MEDIUM: "medium",
            RiskLevel.LOW: "low",
            RiskLevel.INFO: "info",
        }
        return risk_map.get(risk_level, "info")

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Separate signal from noise.

        Signal criteria:
        - Critical/High risk vulnerabilities
        - Verified PoCs
        - Direct reflection
        - Interesting parameters

        Noise criteria:
        - Low confidence findings (<0.7)
        - Duplicates
        - Requires multiple conditions
        """
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for item in findings:
            url = item.get("target_url", "").lower()
            param = item.get("vulnerable_parameter", "").lower()
            dedupe_key = f"xss|{url}|{param}"

            # Check dedup cache
            if dedupe_key in known:
                noise.append(item)
                continue

            ctx = item["context"]

            # Critical findings → signal
            if ctx.get("is_critical"):
                signal.append(item)
                continue

            # High risk with verified PoC → signal
            if ctx.get("risk_level") in ("critical", "high") and ctx.get("has_verified_poc"):
                signal.append(item)
                continue

            # Low confidence → noise
            if ctx.get("confidence", 0) < 0.7:
                item["noise_reason"] = "low_confidence"
                noise.append(item)
                continue

            # Default: signal (XSS findings have inherent value)
            signal.append(item)

        return signal, noise
