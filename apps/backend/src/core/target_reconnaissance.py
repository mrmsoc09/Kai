"""
Target reconnaissance and tech stack fingerprinting.
Detects technologies, frameworks, versions, and services running on target.
"""

from __future__ import annotations

import logging
import httpx
import re
from typing import Any, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class TechStackFingerprint:
    """Detected technology stack for a target."""

    target: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Web servers
    web_servers: Set[str] = field(default_factory=set)

    # Languages and runtimes
    languages: Set[str] = field(default_factory=set)

    # Web frameworks
    frameworks: Set[str] = field(default_factory=set)

    # Databases
    databases: Set[str] = field(default_factory=set)

    # Operating systems
    operating_systems: Set[str] = field(default_factory=set)

    # Services and tools
    services: Set[str] = field(default_factory=set)

    # CMS platforms
    cms_platforms: Set[str] = field(default_factory=set)

    # CDNs and reverse proxies
    cdns: Set[str] = field(default_factory=set)

    # Detected versions
    versions: Dict[str, str] = field(default_factory=dict)

    # Raw headers for additional analysis
    headers: Dict[str, str] = field(default_factory=dict)

    # Open ports detected (if port scanning performed)
    open_ports: Set[int] = field(default_factory=set)

    # SSL/TLS info
    ssl_info: Dict[str, Any] = field(default_factory=dict)

    # Confidence score (0-100)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert fingerprint to dict."""
        return {
            "target": self.target,
            "timestamp": self.timestamp,
            "web_servers": list(self.web_servers),
            "languages": list(self.languages),
            "frameworks": list(self.frameworks),
            "databases": list(self.databases),
            "operating_systems": list(self.operating_systems),
            "services": list(self.services),
            "cms_platforms": list(self.cms_platforms),
            "cdns": list(self.cdns),
            "versions": self.versions,
            "open_ports": sorted(list(self.open_ports)),
            "ssl_info": self.ssl_info,
            "confidence": self.confidence,
        }


class TargetReconnaissanceEngine:
    """
    Fingerprints target technology stack through multiple detection methods:
    - HTTP header analysis
    - Banner grabbing
    - HTML source analysis
    - SSL certificate inspection
    - Common path/file detection
    """

    def __init__(self, timeout: int = 10):
        """Initialize reconnaissance engine."""
        self.timeout = timeout
        self.http_client: Optional[httpx.AsyncClient] = None

        # Technology signatures
        self.web_server_signatures = {
            "nginx": [r"nginx(?:/([0-9.]+))?", "Server: nginx"],
            "apache": [r"apache(?:/([0-9.]+))?", "Server: Apache"],
            "iis": [r"iis(?:/([0-9.]+))?", "Server: Microsoft-IIS"],
            "caddy": [r"caddy", "Server: Caddy"],
            "lighttpd": [r"lighttpd", "Server: lighttpd"],
        }

        self.framework_signatures = {
            "django": [r"django", r"CSRFToken"],
            "flask": [r"flask", r"Werkzeug"],
            "rails": [r"rails", r"action_?controller"],
            "laravel": [r"laravel", r"XSRF-TOKEN"],
            "spring": [r"spring", r"springframework"],
            "express": [r"express", r"x-powered-by"],
            "fastapi": [r"fastapi", r"starlette"],
            "next": [r"next\.js", r"__next"],
            "react": [r"react", r"root.*id"],
            "vue": [r"vue", r"v-app"],
            "angular": [r"angular", r"ng-app"],
        }

        self.cms_signatures = {
            "wordpress": [r"wordpress", r"wp-content", r"wp-includes"],
            "drupal": [r"drupal", r"sites/default/files"],
            "joomla": [r"joomla", r"components/com_"],
            "magento": [r"magento", r"media/catalog"],
        }

        self.database_signatures = {
            "postgresql": ["postgres", "pgsql"],
            "mysql": ["mysql", "mariadb"],
            "mongodb": ["mongo"],
            "redis": ["redis"],
            "elasticsearch": ["elastic"],
            "dynamodb": ["dynamodb"],
        }

    async def fingerprint_target(self, target: str) -> TechStackFingerprint:
        """
        Fingerprint target technology stack.

        Args:
            target: Target URL (e.g., https://example.com)

        Returns:
            TechStackFingerprint with detected technologies
        """
        fp = TechStackFingerprint(target=target)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    target, follow_redirects=True, verify=False
                )

                # Store headers
                fp.headers = dict(response.headers)

                # Analyze headers
                self._analyze_headers(response.headers, fp)

                # Analyze response content
                self._analyze_content(response.text, fp)

                # Check for SSL info
                self._analyze_ssl(response, fp)

                # Check common paths
                await self._check_common_paths(client, target, fp)

        except Exception as e:
            logger.warning(f"Error fingerprinting {target}: {str(e)}")

        # Calculate confidence based on findings
        fp.confidence = self._calculate_confidence(fp)
        return fp

    def _analyze_headers(
        self, headers: dict[str, str], fp: TechStackFingerprint
    ) -> None:
        """Analyze HTTP response headers for tech detection."""
        headers_lower = {k.lower(): v for k, v in headers.items()}

        # Server header
        if "server" in headers_lower:
            server = headers_lower["server"]
            fp.headers["server"] = server
            self._match_signatures(server, self.web_server_signatures, fp)

        # X-Powered-By header
        if "x-powered-by" in headers_lower:
            powered_by = headers_lower["x-powered-by"]
            self._match_signatures(powered_by, self.framework_signatures, fp)

        # X-AspNet-Version (ASP.NET indicator)
        if "x-aspnet-version" in headers_lower:
            fp.languages.add("csharp")
            fp.frameworks.add("asp.net")

        # X-Runtime (Ruby indicator)
        if "x-runtime" in headers_lower:
            fp.languages.add("ruby")

        # Strict-Transport-Security (mature HTTPS)
        if "strict-transport-security" in headers_lower:
            fp.services.add("hsts")

        # Content-Security-Policy
        if "content-security-policy" in headers_lower:
            fp.services.add("csp")

        # CDN detection
        for cdn in ["cloudflare", "akamai", "fastly", "cloudfront"]:
            for header, value in headers_lower.items():
                if cdn in value.lower():
                    fp.cdns.add(cdn)

    def _analyze_content(self, content: str, fp: TechStackFingerprint) -> None:
        """Analyze HTML/JavaScript content for tech detection."""
        content_lower = content.lower()

        # CMS detection
        for cms, patterns in self.cms_signatures.items():
            for pattern in patterns:
                if pattern.lower() in content_lower:
                    fp.cms_platforms.add(cms)
                    break

        # Framework detection via JavaScript
        for framework, patterns in self.framework_signatures.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    fp.frameworks.add(framework)

        # Language detection via comments/meta
        if "x-ua-compatible" in content_lower:
            fp.languages.add("javascript")

        # Backbone.js
        if "backbone" in content_lower:
            fp.frameworks.add("backbone")

        # jQuery
        if "jquery" in content_lower:
            fp.frameworks.add("jquery")

        # Bootstrap
        if "bootstrap" in content_lower:
            fp.frameworks.add("bootstrap")

        # Detect version patterns
        version_patterns = [
            (r"v(\d+\.\d+\.\d+)", None),
            (r"version[=:\s]+(\d+\.\d+(?:\.\d+)?)", None),
        ]
        for pattern, tech in version_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches and tech:
                fp.versions[tech] = matches[0]

    def _analyze_ssl(self, response, fp: TechStackFingerprint) -> None:
        """Analyze SSL/TLS certificate information."""
        try:
            # httpx doesn't expose cert easily, but we can check protocol
            if hasattr(response, "http_version"):
                fp.ssl_info["http_version"] = response.http_version
                if "h2" in response.http_version.lower():
                    fp.services.add("http2")
        except Exception:
            pass

    async def _check_common_paths(
        self, client: httpx.AsyncClient, target: str, fp: TechStackFingerprint
    ) -> None:
        """Check for common paths to detect technologies."""
        common_paths = {
            "admin": ["admin", "administrator", "wp-admin", "admin.php"],
            "api": ["api", "api/v1", "rest/api"],
            "config": [".env", "config.php", "web.config"],
            "files": [".git", ".svn", "uploads"],
        }

        for category, paths in common_paths.items():
            for path in paths:
                try:
                    url = f"{target.rstrip('/')}/{path}"
                    resp = await client.head(url, follow_redirects=False)
                    if resp.status_code != 404:
                        fp.services.add(f"exposed_{category}")
                        break
                except Exception:
                    pass

    def _match_signatures(
        self,
        text: str,
        signatures: Dict[str, list[str]],
        fp: TechStackFingerprint,
    ) -> None:
        """Match text against technology signatures."""
        for tech, patterns in signatures.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # Extract version if pattern contains groups
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match and match.groups():
                        fp.versions[tech] = match.group(1)

                    # Determine tech category
                    if tech in self.web_server_signatures:
                        fp.web_servers.add(tech)
                    elif tech in self.framework_signatures:
                        fp.frameworks.add(tech)
                    elif tech in self.cms_signatures:
                        fp.cms_platforms.add(tech)

    @staticmethod
    def _calculate_confidence(fp: TechStackFingerprint) -> float:
        """
        Calculate fingerprinting confidence score (0-100).
        Based on number and variety of detections.
        """
        score = 0.0
        detections = (
            len(fp.web_servers)
            + len(fp.frameworks)
            + len(fp.languages)
            + len(fp.databases)
        )

        # Base score from detections
        score += min(detections * 15, 60)

        # Bonus for versions
        score += min(len(fp.versions) * 10, 20)

        # Bonus for variety
        if fp.web_servers and fp.frameworks and fp.languages:
            score += 20

        return min(score, 100.0)

    def get_detection_summary(self, fp: TechStackFingerprint) -> str:
        """Get human-readable summary of detections."""
        parts = []

        if fp.web_servers:
            parts.append(f"Web: {', '.join(fp.web_servers)}")
        if fp.languages:
            parts.append(f"Languages: {', '.join(fp.languages)}")
        if fp.frameworks:
            parts.append(f"Frameworks: {', '.join(fp.frameworks)}")
        if fp.cms_platforms:
            parts.append(f"CMS: {', '.join(fp.cms_platforms)}")
        if fp.databases:
            parts.append(f"DB: {', '.join(fp.databases)}")
        if fp.cdns:
            parts.append(f"CDN: {', '.join(fp.cdns)}")

        return " | ".join(parts) if parts else "No technologies detected"
