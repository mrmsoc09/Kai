"""
CVE-specific pattern matching and classification.
Maps CVE data to appropriate detection patterns.
"""

import re
from typing import Optional, List
from ..models.template_models import CVEData, Severity


class CVEPatternMatcher:
    """
    Analyzes CVE descriptions and metadata to suggest
    appropriate detection patterns and severity.
    """
    
    # Keyword mappings for vulnerability classification
    CLASSIFICATION_KEYWORDS = {
        "sql injection": ["sqli", "injection", "database"],
        "sql command": ["sqli", "injection"],
        "cross-site scripting": ["xss", "injection", "cross-site"],
        "xss": ["xss", "injection"],
        "remote code execution": ["rce", "code-execution", "remote"],
        "rce": ["rce", "code-execution"],
        "command injection": ["rce", "command-injection", "injection"],
        "arbitrary code": ["rce", "code-execution"],
        "local file inclusion": ["lfi", "traversal"],
        "lfi": ["lfi", "traversal"],
        "path traversal": ["lfi", "traversal", "path-traversal"],
        "directory traversal": ["lfi", "traversal", "path-traversal"],
        "xml external entity": ["xxe", "xml", "injection"],
        "xxe": ["xxe", "xml"],
        "server-side request forgery": ["ssrf", "server-side"],
        "ssrf": ["ssrf", "server-side"],
        "authentication bypass": ["auth-bypass", "authentication"],
        "privilege escalation": ["privesc", "privilege-escalation"],
        "information disclosure": ["info-disclosure", "exposure"],
        "denial of service": ["dos", "denial-of-service"],
        "buffer overflow": ["buffer-overflow", "memory"],
        "deserialization": ["deserialization", "rce"],
        "open redirect": ["redirect", "open-redirect"],
        "csrf": ["csrf", "cross-site-request-forgery"],
        "clickjacking": ["clickjacking", "ui-redressing"],
        "cors": ["cors", "misconfiguration"],
    }
    
    SEVERITY_MAP = {
        "remote code execution": Severity.CRITICAL,
        "rce": Severity.CRITICAL,
        "sql injection": Severity.CRITICAL,
        "sqli": Severity.CRITICAL,
        "authentication bypass": Severity.HIGH,
        "privilege escalation": Severity.HIGH,
        "xss": Severity.HIGH,
        "ssrf": Severity.HIGH,
        "xxe": Severity.CRITICAL,
        "lfi": Severity.HIGH,
        "path traversal": Severity.MEDIUM,
        "information disclosure": Severity.MEDIUM,
        "denial of service": Severity.LOW,
        "dos": Severity.LOW,
    }
    
    def analyze(self, cve_data: CVEData) -> dict:
        """
        Analyze CVE data and return template generation hints.
        
        Returns:
            Dict containing suggested patterns, severity, tags, etc.
        """
        description_lower = cve_data.description.lower()
        tags = set()
        suggested_patterns = []
        severity = Severity.HIGH  # default
        
        # Analyze description for keywords
        for keyword, tag_list in self.CLASSIFICATION_KEYWORDS.items():
            if keyword in description_lower:
                tags.update(tag_list)
                suggested_patterns.extend(self._get_patterns_for_keyword(keyword))
                # Update severity if more severe
                if keyword in self.SEVERITY_MAP:
                    severity = self._max_severity(severity, self.SEVERITY_MAP[keyword])
        
        # Check CVSS score if available
        if cve_data.cvss_score:
            severity = self._cvss_to_severity(cve_data.cvss_score)
            
        return {
            "tags": list(tags),
            "suggested_patterns": list(set(suggested_patterns)),
            "severity": severity,
            "cwe": self._extract_cwe(description_lower),
            "techniques": self._extract_techniques(description_lower)
        }
    
    def _get_patterns_for_keyword(self, keyword: str) -> List[str]:
        """Map keywords to pattern library names."""
        mapping = {
            "sql injection": ["sqli_error_based"],
            "sqli": ["sqli_error_based"],
            "cross-site scripting": ["xss_reflected"],
            "xss": ["xss_reflected"],
            "remote code execution": ["rce_basic"],
            "rce": ["rce_basic"],
            "command injection": ["rce_basic"],
            "local file inclusion": ["lfi_unix"],
            "lfi": ["lfi_unix"],
            "path traversal": ["lfi_unix"],
            "xml external entity": ["xxe_detection"],
            "xxe": ["xxe_detection"],
            "server-side request forgery": ["ssrf_detection"],
            "ssrf": ["ssrf_detection"],
            "information disclosure": ["info_disclosure"],
        }
        return mapping.get(keyword, [])
    
    def _cvss_to_severity(self, score: float) -> Severity:
        """Convert CVSS score to Nuclei severity."""
        if score >= 9.0:
            return Severity.CRITICAL
        elif score >= 7.0:
            return Severity.HIGH
        elif score >= 4.0:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    def _max_severity(self, s1: Severity, s2: Severity) -> Severity:
        """Return the more severe of two severities."""
        order = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        return s1 if order.index(s1) > order.index(s2) else s2
    
    def _extract_cwe(self, description: str) -> Optional[str]:
        """Extract CWE reference from description."""
        patterns = [
            r'CWE-(\d+)',
            r'CWE[:_](\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return f"CWE-{match.group(1)}"
        return None
    
    def _extract_techniques(self, description: str) -> List[str]:
        """Extract MITRE ATT&CK techniques if mentioned."""
        # Simple extraction for demonstration
        techniques = []
        if "phishing" in description:
            techniques.append("T1566")
        if "privilege escalation" in description:
            techniques.append("T1068")
        return techniques
