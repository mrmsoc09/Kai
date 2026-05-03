"""
Natural Language Processing (NLP) parser for vulnerability descriptions.
Extracts technical details from unstructured text.
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ParsedDescription:
    """Structured data extracted from description."""
    vulnerability_type: Optional[str]
    affected_component: Optional[str]
    affected_versions: List[str]
    attack_vector: Optional[str]
    prerequisites: List[str]
    indicators: List[str]
    confidence: float  # 0.0 to 1.0


class DescriptionParser:
    """
    Parses unstructured vulnerability descriptions to extract
    technical details for template generation.
    Uses regex patterns and heuristics (can be enhanced with ML).
    """
    
    # Patterns for extraction
    VERSION_PATTERNS = [
        r'version[s]? (\d+\.[\d\.]+)',
        r'(\d+\.[\d\.]+) and earlier',
        r'before (\d+\.[\d\.]+)',
        r'(\d+\.[\d\.]+)\+',
        r'v?(\d+\.[\d\.]+)',
    ]
    
    COMPONENT_PATTERNS = [
        r'component[s]? ([\w\s\-]+)',
        r'plugin[s]? ([\w\s\-]+)',
        r'module[s]? ([\w\s\-]+)',
        r'endpoint[s]? ([\w\s\-\/]+)',
        r'parameter[s]? ([\w\s\-]+)',
        r'function[s]? ([\w\s\-]+)',
    ]
    
    ATTACK_VECTORS = [
        "remote", "local", "network", "authenticated", "unauthenticated",
        "physical", "adjacent", "context-dependent"
    ]
    
    def __init__(self):
        self.vuln_keywords = {
            "injection": ["injection", "inject", "sql", "command", "code"],
            "overflow": ["overflow", "buffer", "heap", "stack"],
            "traversal": ["traversal", "path", "directory", "file inclusion"],
            "execution": ["execution", "rce", "remote code", "command execution"],
            "disclosure": ["disclosure", "exposure", "leak", "information"],
            "bypass": ["bypass", "circumvent", "authentication bypass"],
            "escalation": ["escalation", "privilege", "elevation"],
            "xss": ["xss", "cross-site scripting", "cross site scripting"],
            "csrf": ["csrf", "cross-site request forgery"],
            "xxe": ["xxe", "xml external entity"],
            "ssrf": ["ssrf", "server-side request forgery"],
        }
    
    def parse(self, description: str) -> ParsedDescription:
        """
        Parse vulnerability description text.
        
        Args:
            description: Raw vulnerability description
            
        Returns:
            ParsedDescription with extracted fields
        """
        text = description.lower()
        
        # Extract vulnerability type
        vuln_type = self._detect_vulnerability_type(text)
        
        # Extract affected component
        component = self._extract_component(description)
        
        # Extract versions
        versions = self._extract_versions(description)
        
        # Detect attack vector
        attack_vector = self._detect_attack_vector(text)
        
        # Extract prerequisites
        prerequisites = self._extract_prerequisites(text)
        
        # Extract indicators (technical signatures)
        indicators = self._extract_indicators(text)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            vuln_type, component, versions, indicators
        )
        
        return ParsedDescription(
            vulnerability_type=vuln_type,
            affected_component=component,
            affected_versions=versions,
            attack_vector=attack_vector,
            prerequisites=prerequisites,
            indicators=indicators,
            confidence=confidence
        )
    
    def _detect_vulnerability_type(self, text: str) -> Optional[str]:
        """Detect vulnerability category from keywords."""
        scores = {}
        for vuln_type, keywords in self.vuln_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[vuln_type] = score
        
        if scores:
            return max(scores, key=scores.get)
        return None
    
    def _extract_component(self, text: str) -> Optional[str]:
        """Extract affected component name."""
        for pattern in self.COMPONENT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: look for quoted strings that might be component names
        quotes = re.findall(r'"([^"]{3,50})"', text)
        if quotes:
            return quotes[0]
        return None
    
    def _extract_versions(self, text: str) -> List[str]:
        """Extract version numbers."""
        versions = []
        for pattern in self.VERSION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            versions.extend(matches)
        return list(set(versions))  # Remove duplicates
    
    def _detect_attack_vector(self, text: str) -> Optional[str]:
        """Determine attack vector from description."""
        if "unauthenticated" in text or "without authentication" in text:
            return "unauthenticated"
        elif "authenticated" in text or "valid credentials" in text:
            return "authenticated"
        elif "remote" in text:
            return "remote"
        elif "local" in text:
            return "local"
        return None
    
    def _extract_prerequisites(self, text: str) -> List[str]:
        """Extract prerequisites or conditions for exploitation."""
        prereqs = []
        
        # Look for common prerequisite indicators
        patterns = [
            r'require[s]? ([^\.]+)',
            r'prerequisite[s]?[^:]*: ([^\.]+)',
            r'condition[s]?[^:]*: ([^\.]+)',
            r'user must ([^\.]+)',
            r'administrator must ([^\.]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            prereqs.extend([m.strip() for m in matches])
            
        return prereqs
    
    def _extract_indicators(self, text: str) -> List[str]:
        """Extract technical indicators or signatures."""
        indicators = []
        
        # Look for HTTP paths/endpoints
        paths = re.findall(r'["\']([\/][\w\/\-\_\.]+)["\']', text)
        indicators.extend(paths)
        
        # Look for parameter names
        params = re.findall(r'parameter[s]? ["\']?([\w\-\_]+)["\']?', text, re.IGNORECASE)
        indicators.extend(params)
        
        # Look for specific strings mentioned
        strings = re.findall(r'string ["\']([^"\']{5,})["\']', text)
        indicators.extend(strings)
        
        return list(set(indicators))
    
    def _calculate_confidence(self, vuln_type, component, versions, indicators) -> float:
        """Calculate confidence score based on extraction completeness."""
        score = 0.0
        if vuln_type:
            score += 0.3
        if component:
            score += 0.3
        if versions:
            score += 0.2
        if indicators:
            score += 0.2
        return min(score, 1.0)
    
    def suggest_matchers(self, parsed: ParsedDescription) -> List[Dict]:
        """
        Suggest Nuclei matchers based on parsed description.
        """
        matchers = []
        
        if parsed.vulnerability_type == "injection":
            matchers.append({
                "type": "regex",
                "part": "body",
                "regex": ["error", "exception", "syntax"],
                "condition": "or"
            })
        elif parsed.vulnerability_type == "disclosure":
            matchers.append({
                "type": "regex",
                "part": "body",
                "regex": ["password", "secret", "key", "token"],
                "condition": "or"
            })
        elif parsed.vulnerability_type == "execution":
            matchers.append({
                "type": "regex",
                "part": "body",
                "regex": ["uid=", "gid=", "root:", "administrator"],
                "condition": "or"
            })
            
        return matchers
