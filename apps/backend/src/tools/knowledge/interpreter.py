"""Tool output interpreter for applying knowledge-driven analysis to raw tool output.

This module interprets raw tool output using structured interpretation rules from
the tool knowledge registry, producing actionable findings with severity, confidence,
and next-step guidance.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from apps.backend.src.tools.knowledge.loader import ToolKnowledgeLoader

logger = logging.getLogger(__name__)


class ToolOutputInterpreter:
    """Applies interpretation rules to raw tool output, returning structured findings."""

    def __init__(self, knowledge_loader: ToolKnowledgeLoader) -> None:
        """Initialize interpreter with reference to ToolKnowledgeLoader.

        Args:
            knowledge_loader: ToolKnowledgeLoader instance providing tool knowledge.
        """
        self.knowledge_loader = knowledge_loader
        self._rule_cache: dict[str, list[str]] = {}

    def interpret_output(
        self,
        tool_name: str,
        raw_output: str,
        target: str = "",
        execution_time: float = 0.0,
    ) -> dict[str, Any]:
        """Apply interpretation rules to raw tool output.

        Args:
            tool_name: Name of tool that produced output (testssl, spiderfoot, etc.).
            raw_output: Raw, unprocessed tool output string.
            target: Optional target/host for context (domain, IP, URL).
            execution_time: Execution time in seconds.

        Returns:
            Dictionary containing:
            - raw_output: Unmodified tool output
            - findings: List of interpreted findings
            - summary: High-level interpretation
            - tool_version: Tool version if detectable
            - execution_time: Time in seconds
            - interpretation_quality: Confidence in overall interpretation (0.0-1.0)
        """
        if not raw_output.strip():
            logger.warning(f"Empty output from {tool_name}")
            return {
                "raw_output": raw_output,
                "findings": [],
                "summary": f"No output from {tool_name}",
                "tool_version": None,
                "execution_time": execution_time,
                "interpretation_quality": 0.0,
            }

        start_time = time.time()

        # Extract key findings from raw output
        extracted_findings = self._extract_key_findings(tool_name, raw_output)

        # Apply interpretation rules
        interpreted_findings = self._apply_interpretation_rules(
            tool_name, raw_output, extracted_findings
        )

        # Detect tool version if possible
        tool_version = self._detect_tool_version(tool_name, raw_output)

        # Generate summary
        summary = self._generate_summary(tool_name, interpreted_findings, target)

        # Calculate interpretation quality
        quality = self._calculate_interpretation_quality(
            tool_name, raw_output, interpreted_findings
        )

        interpretation_time = time.time() - start_time

        return {
            "raw_output": raw_output,
            "findings": interpreted_findings,
            "summary": summary,
            "tool_version": tool_version,
            "execution_time": execution_time,
            "interpretation_time": interpretation_time,
            "interpretation_quality": quality,
        }

    def _extract_key_findings(self, tool_name: str, raw_output: str) -> list[str]:
        """Extract key findings from raw output using tool-specific patterns.

        Args:
            tool_name: Name of the tool.
            raw_output: Raw tool output.

        Returns:
            List of extracted finding strings.
        """
        findings: list[str] = []

        if tool_name == "testssl":
            findings.extend(self._extract_testssl_findings(raw_output))
        elif tool_name == "spiderfoot":
            findings.extend(self._extract_spiderfoot_findings(raw_output))
        elif tool_name == "graphql-cop":
            findings.extend(self._extract_graphqlcop_findings(raw_output))
        else:
            # Generic extraction for unknown tools
            findings.extend(self._extract_generic_findings(raw_output))

        return findings

    def _extract_testssl_findings(self, raw_output: str) -> list[str]:
        """Extract findings specific to testssl.sh output."""
        findings: list[str] = []

        # Extract cipher grades
        for match in re.finditer(r"Cipher.*?Grade\s+([A-F])", raw_output, re.IGNORECASE):
            grade = match.group(1)
            findings.append(f"Cipher Grade {grade}")

        # Extract certificate issues
        if "certificate" in raw_output.lower():
            for match in re.finditer(
                r"(certificate|cert).*?(expired|invalid|self-signed|wrong host)",
                raw_output,
                re.IGNORECASE,
            ):
                findings.append(match.group(0)[:100])

        # Extract protocol versions
        for protocol in ["TLS 1.3", "TLS 1.2", "TLS 1.1", "TLS 1.0", "SSLv3", "SSLv2"]:
            if protocol in raw_output:
                findings.append(f"Protocol {protocol} supported")

        # Extract vulnerability indicators
        for vuln in ["Heartbleed", "POODLE", "CRIME", "BEAST", "CCS", "Renegotiation"]:
            if vuln.lower() in raw_output.lower():
                findings.append(f"Potential {vuln} vulnerability")

        # Extract HSTS/OCSP status
        if "HSTS" in raw_output:
            findings.append("HSTS configuration detected")
        if "OCSP" in raw_output:
            findings.append("OCSP configuration detected")

        return findings

    def _extract_spiderfoot_findings(self, raw_output: str) -> list[str]:
        """Extract findings specific to spiderfoot output."""
        findings: list[str] = []

        # Extract discovered entities (subdomains, emails, IPs)
        for match in re.finditer(
            r"(subdomain|email|ip|domain|host|dns|asn):\s*([^\s\n]+)", raw_output, re.IGNORECASE
        ):
            entity_type = match.group(1)
            entity_value = match.group(2)
            findings.append(f"{entity_type}: {entity_value}")

        # Extract zone transfer results
        if "zone transfer" in raw_output.lower():
            findings.append("Zone transfer successful")

        # Extract WHOIS results
        if "whois" in raw_output.lower():
            findings.append("WHOIS information discovered")

        # Extract certificate transparency findings
        if "certificate" in raw_output.lower() or "cert" in raw_output.lower():
            findings.append("Certificate transparency information found")

        # Extract DNS misconfiguration
        for issue in ["DNS allow-all", "DNS open resolver", "DNS amplification"]:
            if issue.lower() in raw_output.lower():
                findings.append(f"DNS issue: {issue}")

        return findings

    def _extract_graphqlcop_findings(self, raw_output: str) -> list[str]:
        """Extract findings specific to graphql-cop output."""
        findings: list[str] = []

        # Extract introspection status
        if "introspection" in raw_output.lower():
            if "enabled" in raw_output.lower() or "allowed" in raw_output.lower():
                findings.append("GraphQL introspection enabled")
            elif "disabled" in raw_output.lower():
                findings.append("GraphQL introspection disabled")

        # Extract query limits
        for limit_type in ["depth", "complexity", "rate"]:
            if limit_type in raw_output.lower():
                if "not" in raw_output.lower() or "no" in raw_output.lower():
                    findings.append(f"No query {limit_type} limit")
                else:
                    findings.append(f"Query {limit_type} limit configured")

        # Extract field-level permissions
        if "permission" in raw_output.lower():
            findings.append("Permission configuration detected")

        # Extract mutation security
        if "mutation" in raw_output.lower():
            findings.append("Mutations detected in schema")

        # Extract batch query support
        if "batch" in raw_output.lower():
            findings.append("Batch queries supported")

        # Extract directive findings
        if "directive" in raw_output.lower():
            findings.append("Custom directives detected")

        return findings

    def _extract_generic_findings(self, raw_output: str) -> list[str]:
        """Generic extraction for unknown tools."""
        findings: list[str] = []

        # Look for common security keywords
        keywords = [
            "vulnerability",
            "critical",
            "high",
            "medium",
            "error",
            "warning",
            "issue",
            "risk",
            "exposure",
        ]

        for keyword in keywords:
            if keyword in raw_output.lower():
                # Find lines containing the keyword
                for line in raw_output.split("\n"):
                    if keyword in line.lower():
                        findings.append(line.strip()[:100])
                        break

        return findings

    def _apply_interpretation_rules(
        self, tool_name: str, raw_output: str, extracted: list[str]
    ) -> list[dict[str, Any]]:
        """Apply interpretation rules from tool knowledge to findings.

        Args:
            tool_name: Name of the tool.
            raw_output: Raw tool output.
            extracted: List of extracted findings.

        Returns:
            List of structured findings with severity, confidence, next steps.
        """
        findings: list[dict[str, Any]] = []

        # Get interpretation rules from knowledge
        try:
            rules = self.knowledge_loader.get_interpretation_rules(tool_name)
        except KeyError:
            logger.warning(f"No interpretation rules for {tool_name}")
            # Create basic findings from extracted data
            for finding in extracted:
                findings.append(
                    {
                        "finding": finding,
                        "category": "unknown",
                        "severity": "INFO",
                        "confidence": 0.5,
                        "evidence": finding,
                        "context": "Extracted from tool output",
                        "next_steps": ["Investigate finding"],
                    }
                )
            return findings

        # Apply each rule to findings
        for extracted_finding in extracted:
            matching_rules = self._find_matching_rules(rules, extracted_finding)

            for rule in matching_rules:
                category = self._categorize_finding(tool_name, extracted_finding)
                severity = self._assess_severity(tool_name, category, extracted_finding)
                confidence = self._calculate_confidence(tool_name, extracted_finding, raw_output)
                next_steps = self._generate_next_steps(tool_name, category, severity)

                finding_obj = {
                    "finding": extracted_finding,
                    "category": category,
                    "severity": severity,
                    "confidence": confidence,
                    "evidence": extracted_finding,
                    "context": rule,
                    "next_steps": next_steps,
                }

                # Avoid duplicates
                if not self._finding_exists(findings, finding_obj):
                    findings.append(finding_obj)

        return findings

    def _find_matching_rules(self, rules: list[str], finding: str) -> list[str]:
        """Find interpretation rules that match a finding.

        Args:
            rules: List of interpretation rules.
            finding: Finding string to match.

        Returns:
            List of matching rules.
        """
        matching = []
        finding_lower = finding.lower()

        for rule in rules:
            rule_lower = rule.lower()
            # Simple keyword matching; could be enhanced with regex
            if any(keyword in finding_lower for keyword in rule_lower.split()[:3]):
                matching.append(rule)

        return matching[:1] if matching else []  # Return at most 1 matching rule

    def _categorize_finding(self, tool_name: str, finding: str) -> str:
        """Categorize finding by type.

        Args:
            tool_name: Name of the tool.
            finding: Finding string.

        Returns:
            Category string (cipher, certificate, protocol, etc.).
        """
        finding_lower = finding.lower()

        # Tool-specific categorization
        if tool_name == "testssl":
            if "cipher" in finding_lower or "grade" in finding_lower:
                return "cipher"
            if (
                "certificate" in finding_lower
                or "cert" in finding_lower
                or "expired" in finding_lower
            ):
                return "certificate"
            if "protocol" in finding_lower or "tls" in finding_lower:
                return "protocol"
            if any(v in finding_lower for v in ["heartbleed", "poodle", "crime", "beast"]):
                return "vulnerability"
            if "hsts" in finding_lower:
                return "hsts"
            if "ocsp" in finding_lower:
                return "ocsp"

        elif tool_name == "spiderfoot":
            if "subdomain" in finding_lower:
                return "subdomain"
            if "email" in finding_lower:
                return "email"
            if "asn" in finding_lower or "ip" in finding_lower:
                return "network"
            if "zone transfer" in finding_lower:
                return "dns_misconfiguration"
            if "whois" in finding_lower:
                return "whois"

        elif tool_name == "graphql-cop":
            if "introspection" in finding_lower:
                return "introspection"
            if "depth" in finding_lower or "complexity" in finding_lower:
                return "query_limits"
            if "permission" in finding_lower:
                return "authorization"
            if "mutation" in finding_lower:
                return "mutation"
            if "batch" in finding_lower:
                return "batch_queries"

        return "unknown"

    def _assess_severity(self, tool_name: str, category: str, finding: str) -> str:
        """Assess severity (CRITICAL, HIGH, MEDIUM, LOW, INFO).

        Args:
            tool_name: Name of the tool.
            category: Finding category.
            finding: Finding string.

        Returns:
            Severity level.
        """
        finding_lower = finding.lower()

        # Critical severity indicators
        critical_keywords = ["critical", "grade f", "heartbleed", "expired", "self-signed"]
        if any(kw in finding_lower for kw in critical_keywords):
            return "CRITICAL"

        # High severity indicators
        high_keywords = [
            "grade e",
            "poodle",
            "crime",
            "beast",
            "zone transfer",
            "no limit",
            "not set",
        ]
        if any(kw in finding_lower for kw in high_keywords):
            return "HIGH"

        # Medium severity indicators
        medium_keywords = [
            "grade c",
            "old protocol",
            "tls 1.0",
            "tls 1.1",
            "no hsts",
            "introspection",
        ]
        if any(kw in finding_lower for kw in medium_keywords):
            return "MEDIUM"

        # Low severity indicators
        low_keywords = ["grade b", "tls 1.2", "deprecated"]
        if any(kw in finding_lower for kw in low_keywords):
            return "LOW"

        return "INFO"

    def _calculate_confidence(self, tool_name: str, finding: str, evidence: str) -> float:
        """Calculate confidence (0.0-1.0) in finding accuracy.

        Args:
            tool_name: Name of the tool.
            finding: Finding string.
            evidence: Supporting evidence from tool output.

        Returns:
            Confidence score (0.0-1.0).
        """
        confidence = 0.5  # Base confidence

        # Increase confidence for direct evidence
        if finding.lower() in evidence.lower():
            confidence += 0.3

        # Tool-specific confidence adjustments
        if tool_name == "testssl":
            # testssl is highly reliable for cipher/protocol detection
            if any(x in finding.lower() for x in ["cipher", "grade", "protocol"]):
                confidence = 0.95
        elif tool_name == "spiderfoot":
            # spiderfoot is reliable for OSINT findings
            if any(x in finding.lower() for x in ["subdomain", "email", "asn"]):
                confidence = 0.90
        elif tool_name == "graphql-cop":
            # graphql-cop is reliable for introspection and limit detection
            if any(x in finding.lower() for x in ["introspection", "limit"]):
                confidence = 0.92

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, confidence))

    def _generate_next_steps(self, tool_name: str, category: str, severity: str) -> list[str]:
        """Generate next steps based on finding type and severity.

        Args:
            tool_name: Name of the tool.
            category: Finding category.
            severity: Severity level.

        Returns:
            List of recommended next steps.
        """
        next_steps: list[str] = []

        # Generic actions based on severity
        if severity == "CRITICAL":
            next_steps.append("Remediate immediately")
            next_steps.append("Escalate to security team")
        elif severity == "HIGH":
            next_steps.append("Schedule remediation")
            next_steps.append("Document risk acceptance if not remediating")
        elif severity == "MEDIUM":
            next_steps.append("Plan remediation")
            next_steps.append("Monitor for exploitation")
        elif severity == "LOW":
            next_steps.append("Consider in next maintenance window")
        else:
            next_steps.append("Log and monitor")

        # Tool and category-specific actions
        if tool_name == "testssl":
            if category == "cipher":
                next_steps.append("Update cipher suite configuration")
            elif category == "certificate":
                next_steps.append("Renew or update certificate")
            elif category == "protocol":
                next_steps.append("Disable deprecated protocols")
        elif tool_name == "spiderfoot":
            if category == "dns_misconfiguration":
                next_steps.append("Review DNS configuration")
            elif category == "subdomain":
                next_steps.append("Assess subdomain for vulnerabilities")
        elif tool_name == "graphql-cop":
            if category == "introspection":
                next_steps.append("Disable GraphQL introspection in production")
            elif category == "query_limits":
                next_steps.append("Implement query complexity/depth limits")
            elif category == "authorization":
                next_steps.append("Review field-level permissions")

        return next_steps if next_steps else ["Investigate finding further"]

    def _detect_tool_version(self, tool_name: str, raw_output: str) -> str | None:
        """Detect tool version from output if possible.

        Args:
            tool_name: Name of the tool.
            raw_output: Raw tool output.

        Returns:
            Version string or None if not detected.
        """
        # Look for version patterns
        for match in re.finditer(
            r"(?:version|v|release)\s*[:\s=]+\s*([0-9]+\.[0-9]+[^\s]*)",
            raw_output,
            re.IGNORECASE,
        ):
            return match.group(1)

        return None

    def _generate_summary(self, tool_name: str, findings: list[dict[str, Any]], target: str) -> str:
        """Generate high-level interpretation summary.

        Args:
            tool_name: Name of the tool.
            findings: List of interpreted findings.
            target: Target being scanned.

        Returns:
            Summary string.
        """
        if not findings:
            return f"No findings from {tool_name}" + (f" on {target}" if target else "")

        # Count by severity
        severity_counts = {}
        for finding in findings:
            severity = finding.get("severity", "INFO")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Build summary
        summary_parts = []
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            count = severity_counts.get(severity, 0)
            if count > 0:
                summary_parts.append(f"{count} {severity}")

        summary = f"{tool_name} found: " + ", ".join(summary_parts)
        if target:
            summary += f" on {target}"

        return summary

    def _calculate_interpretation_quality(
        self, tool_name: str, raw_output: str, findings: list[dict[str, Any]]
    ) -> float:
        """Calculate overall quality of interpretation (0.0-1.0).

        Args:
            tool_name: Name of the tool.
            raw_output: Raw tool output.
            findings: List of interpreted findings.

        Returns:
            Quality score (0.0-1.0).
        """
        if not raw_output.strip():
            return 0.0

        if not findings:
            return 0.5  # Moderate quality if no findings extracted

        # Quality increases with number of findings (more thorough)
        quality = min(0.7, len(findings) * 0.1)

        # Quality increases with confidence of findings
        avg_confidence = sum(f.get("confidence", 0.5) for f in findings) / len(findings)
        quality += avg_confidence * 0.2

        # Known tools have higher quality
        if tool_name in ["testssl", "spiderfoot", "graphql-cop"]:
            quality += 0.1

        return min(1.0, quality)

    @staticmethod
    def _finding_exists(findings: list[dict[str, Any]], new_finding: dict[str, Any]) -> bool:
        """Check if finding already exists in list (deduplication).

        Args:
            findings: List of existing findings.
            new_finding: New finding to check.

        Returns:
            True if finding exists, False otherwise.
        """
        for existing in findings:
            if existing.get("finding") == new_finding.get("finding") and existing.get(
                "category"
            ) == new_finding.get("category"):
                return True
        return False
