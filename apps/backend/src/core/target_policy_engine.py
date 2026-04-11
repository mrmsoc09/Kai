"""
Target Policy Engine for Rules of Engagement (RoE) validation.
Enforces scope constraints, CIDR allowlists, domain restrictions before execution.
"""

from __future__ import annotations

import logging
import ipaddress
from typing import Any, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import re

logger = logging.getLogger(__name__)


class TargetType(str, Enum):
    """Type of target."""

    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IPv4 = "ipv4"
    IPv6 = "ipv6"
    CIDR = "cidr"
    URL = "url"
    EMAIL = "email"


class ScopeStatus(str, Enum):
    """Scope validation status."""

    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    REQUIRES_APPROVAL = "requires_approval"
    RESTRICTED = "restricted"


@dataclass
class ScopePolicy:
    """Scope policy configuration."""

    allowlisted_domains: Set[str] = None
    allowlisted_cidrs: Set[str] = None
    denylisted_domains: Set[str] = None
    denylisted_cidrs: Set[str] = None
    denylisted_patterns: Set[str] = None
    require_approval_domains: Set[str] = None
    approved_subdomains_only: bool = False
    allow_internal_ips: bool = False
    max_scope_expansion: int = 100  # Max subdomains/IPs from single domain

    def __post_init__(self):
        if self.allowlisted_domains is None:
            self.allowlisted_domains = set()
        if self.allowlisted_cidrs is None:
            self.allowlisted_cidrs = set()
        if self.denylisted_domains is None:
            self.denylisted_domains = set()
        if self.denylisted_cidrs is None:
            self.denylisted_cidrs = set()
        if self.denylisted_patterns is None:
            self.denylisted_patterns = set()
        if self.require_approval_domains is None:
            self.require_approval_domains = set()


class TargetPolicyEngine:
    """
    Validates targets against Rules of Engagement (RoE).
    Checks CIDR ranges, domain allowlists, denylist patterns.
    """

    def __init__(self, policy: Optional[ScopePolicy] = None):
        """
        Initialize policy engine.

        Args:
            policy: ScopePolicy object
        """
        self.policy = policy or ScopePolicy()
        self.validation_cache: Dict[str, ScopeStatus] = {}
        self.validation_log: list[Dict[str, Any]] = []

    def validate_target(
        self, target: str
    ) -> Tuple[ScopeStatus, str]:
        """
        Validate target against RoE policy.

        Args:
            target: Target (domain, IP, CIDR, URL, email)

        Returns:
            Tuple of (ScopeStatus, explanation_string)
        """
        # Check cache
        if target in self.validation_cache:
            status = self.validation_cache[target]
            return status, f"Cached: {status.value}"

        # Determine target type
        target_type, target_normalized = self._identify_target_type(
            target
        )

        # Run validation pipeline
        status, reason = self._validate_by_type(
            target_type, target_normalized
        )

        # Cache result
        self.validation_cache[target] = status

        # Log
        self.validation_log.append(
            {
                "target": target,
                "target_type": target_type.value,
                "status": status.value,
                "reason": reason,
            }
        )

        logger.info(f"Target validation: {target} → {status.value}")
        return status, reason

    def _identify_target_type(
        self, target: str
    ) -> Tuple[TargetType, str]:
        """Identify target type."""
        target = target.strip()

        # URL
        if target.startswith("http://") or target.startswith(
            "https://"
        ):
            return TargetType.URL, target

        # Email
        if "@" in target and "." in target:
            return TargetType.EMAIL, target

        # IPv4
        try:
            ipaddress.IPv4Address(target)
            return TargetType.IPv4, target
        except (ipaddress.AddressValueError, ValueError):
            pass

        # IPv6
        try:
            ipaddress.IPv6Address(target)
            return TargetType.IPv6, target
        except (ipaddress.AddressValueError, ValueError):
            pass

        # CIDR
        if "/" in target:
            try:
                ipaddress.ip_network(target, strict=False)
                return TargetType.CIDR, target
            except (ipaddress.AddressValueError, ValueError):
                pass

        # Subdomain or domain
        if "." in target:
            parts = target.split(".")
            if len(parts) > 2:
                return TargetType.SUBDOMAIN, target
            return TargetType.DOMAIN, target

        # Default: treat as domain
        return TargetType.DOMAIN, target

    def _validate_by_type(
        self, target_type: TargetType, target: str
    ) -> Tuple[ScopeStatus, str]:
        """Validate target by type."""
        if target_type == TargetType.DOMAIN:
            return self._validate_domain(target)
        elif target_type == TargetType.SUBDOMAIN:
            return self._validate_subdomain(target)
        elif target_type == TargetType.IPv4:
            return self._validate_ipv4(target)
        elif target_type == TargetType.IPv6:
            return self._validate_ipv6(target)
        elif target_type == TargetType.CIDR:
            return self._validate_cidr(target)
        elif target_type == TargetType.URL:
            return self._validate_url(target)
        elif target_type == TargetType.EMAIL:
            return self._validate_email(target)
        else:
            return ScopeStatus.OUT_OF_SCOPE, "Unknown target type"

    def _validate_domain(
        self, domain: str
    ) -> Tuple[ScopeStatus, str]:
        """Validate domain against policy."""
        domain_lower = domain.lower()

        # Check denylist patterns
        for pattern in self.policy.denylisted_patterns:
            if re.search(pattern, domain_lower):
                return (
                    ScopeStatus.RESTRICTED,
                    f"Matches denied pattern: {pattern}",
                )

        # Check explicit denylist
        if domain_lower in self.policy.denylisted_domains:
            return (
                ScopeStatus.RESTRICTED,
                "Domain explicitly denied",
            )

        # Check allowlist
        if domain_lower in self.policy.allowlisted_domains:
            return (
                ScopeStatus.IN_SCOPE,
                "Domain in allowlist",
            )

        # Check approval-required list
        if domain_lower in self.policy.require_approval_domains:
            return (
                ScopeStatus.REQUIRES_APPROVAL,
                "Domain requires approval",
            )

        # Default: out of scope
        return (
            ScopeStatus.OUT_OF_SCOPE,
            "Domain not in allowlist",
        )

    def _validate_subdomain(
        self, subdomain: str
    ) -> Tuple[ScopeStatus, str]:
        """Validate subdomain against policy."""
        subdomain_lower = subdomain.lower()

        # Extract base domain
        parts = subdomain_lower.split(".")
        base_domain = ".".join(parts[-2:])

        if self.policy.approved_subdomains_only:
            # Only explicitly listed subdomains allowed
            if subdomain_lower in self.policy.allowlisted_domains:
                return (
                    ScopeStatus.IN_SCOPE,
                    "Subdomain in allowlist",
                )
            return (
                ScopeStatus.OUT_OF_SCOPE,
                "Only approved subdomains allowed",
            )

        # Allow if base domain is in allowlist
        if base_domain in self.policy.allowlisted_domains:
            return (
                ScopeStatus.IN_SCOPE,
                f"Base domain {base_domain} in allowlist",
            )

        # Check denylist
        for denied in self.policy.denylisted_domains:
            if subdomain_lower.endswith(denied):
                return (
                    ScopeStatus.RESTRICTED,
                    f"Parent domain {denied} denied",
                )

        return (
            ScopeStatus.OUT_OF_SCOPE,
            "Subdomain's base domain not in allowlist",
        )

    def _validate_ipv4(
        self, ipv4: str
    ) -> Tuple[ScopeStatus, str]:
        """Validate IPv4 against policy."""
        try:
            ip_obj = ipaddress.IPv4Address(ipv4)

            # Check private IP restriction
            if ip_obj.is_private and not self.policy.allow_internal_ips:
                return (
                    ScopeStatus.RESTRICTED,
                    "Private IP addresses not allowed",
                )

            # Check CIDR allowlist
            for cidr_str in self.policy.allowlisted_cidrs:
                try:
                    cidr_obj = ipaddress.ip_network(
                        cidr_str, strict=False
                    )
                    if ip_obj in cidr_obj:
                        return (
                            ScopeStatus.IN_SCOPE,
                            f"IP in allowed CIDR {cidr_str}",
                        )
                except (ipaddress.AddressValueError, ValueError):
                    pass

            # Check CIDR denylist
            for cidr_str in self.policy.denylisted_cidrs:
                try:
                    cidr_obj = ipaddress.ip_network(
                        cidr_str, strict=False
                    )
                    if ip_obj in cidr_obj:
                        return (
                            ScopeStatus.RESTRICTED,
                            f"IP in denied CIDR {cidr_str}",
                        )
                except (ipaddress.AddressValueError, ValueError):
                    pass

            return (
                ScopeStatus.OUT_OF_SCOPE,
                "IP not in allowlist CIDRs",
            )

        except (ipaddress.AddressValueError, ValueError):
            return (
                ScopeStatus.OUT_OF_SCOPE,
                "Invalid IPv4 address",
            )

    def _validate_ipv6(
        self, ipv6: str
    ) -> Tuple[ScopeStatus, str]:
        """Validate IPv6 against policy."""
        try:
            ip_obj = ipaddress.IPv6Address(ipv6)

            # Check private IP restriction
            if ip_obj.is_private and not self.policy.allow_internal_ips:
                return (
                    ScopeStatus.RESTRICTED,
                    "Private IPv6 addresses not allowed",
                )

            # Similar to IPv4 validation
            for cidr_str in self.policy.allowlisted_cidrs:
                try:
                    cidr_obj = ipaddress.ip_network(
                        cidr_str, strict=False
                    )
                    if ip_obj in cidr_obj:
                        return (
                            ScopeStatus.IN_SCOPE,
                            f"IPv6 in allowed CIDR {cidr_str}",
                        )
                except (ipaddress.AddressValueError, ValueError):
                    pass

            return (
                ScopeStatus.OUT_OF_SCOPE,
                "IPv6 not in allowlist CIDRs",
            )

        except (ipaddress.AddressValueError, ValueError):
            return (
                ScopeStatus.OUT_OF_SCOPE,
                "Invalid IPv6 address",
            )

    def _validate_cidr(
        self, cidr: str
    ) -> Tuple[ScopeStatus, str]:
        """Validate CIDR block against policy."""
        try:
            cidr_obj = ipaddress.ip_network(cidr, strict=False)

            # Must be in allowlist
            for allowed_cidr_str in self.policy.allowlisted_cidrs:
                try:
                    allowed_cidr = ipaddress.ip_network(
                        allowed_cidr_str, strict=False
                    )
                    # Check if requested CIDR is subset of allowed
                    if cidr_obj.subnet_of(allowed_cidr):
                        return (
                            ScopeStatus.IN_SCOPE,
                            f"CIDR is within allowed {allowed_cidr_str}",
                        )
                except (ipaddress.AddressValueError, ValueError):
                    pass

            return (
                ScopeStatus.OUT_OF_SCOPE,
                "CIDR not subset of allowlist",
            )

        except (ipaddress.AddressValueError, ValueError):
            return (
                ScopeStatus.OUT_OF_SCOPE,
                "Invalid CIDR notation",
            )

    def _validate_url(
        self, url: str
    ) -> Tuple[ScopeStatus, str]:
        """Validate URL by extracting domain and validating."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            hostname = parsed.hostname

            if not hostname:
                return (
                    ScopeStatus.OUT_OF_SCOPE,
                    "Could not extract hostname from URL",
                )

            # Validate hostname
            return self.validate_target(hostname)

        except Exception as e:
            return (
                ScopeStatus.OUT_OF_SCOPE,
                f"URL parsing error: {str(e)}",
            )

    def _validate_email(
        self, email: str
    ) -> Tuple[ScopeStatus, str]:
        """Validate email by extracting domain and validating."""
        try:
            domain = email.split("@")[1]
            return self.validate_target(domain)
        except Exception:
            return (
                ScopeStatus.OUT_OF_SCOPE,
                "Invalid email format",
            )

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary statistics."""
        in_scope = sum(
            1
            for log in self.validation_log
            if log["status"] == ScopeStatus.IN_SCOPE.value
        )
        out_of_scope = sum(
            1
            for log in self.validation_log
            if log["status"] == ScopeStatus.OUT_OF_SCOPE.value
        )
        requires_approval = sum(
            1
            for log in self.validation_log
            if log["status"]
            == ScopeStatus.REQUIRES_APPROVAL.value
        )
        restricted = sum(
            1
            for log in self.validation_log
            if log["status"] == ScopeStatus.RESTRICTED.value
        )

        return {
            "total_validations": len(self.validation_log),
            "in_scope": in_scope,
            "out_of_scope": out_of_scope,
            "requires_approval": requires_approval,
            "restricted": restricted,
            "allowlisted_domains": list(
                self.policy.allowlisted_domains
            ),
            "allowlisted_cidrs": list(self.policy.allowlisted_cidrs),
            "denylisted_domains": list(
                self.policy.denylisted_domains
            ),
            "denylisted_cidrs": list(self.policy.denylisted_cidrs),
        }


# Global policy engine instance
_policy_engine: Optional[TargetPolicyEngine] = None


def get_target_policy_engine() -> TargetPolicyEngine:
    """Get or create global policy engine."""
    global _policy_engine

    if _policy_engine is None:
        _policy_engine = TargetPolicyEngine()

    return _policy_engine


def load_policy_from_config(
    config_path: str = "config/scope_guardrails.yaml",
) -> TargetPolicyEngine:
    """Load policy from config file."""
    import yaml

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        policy = ScopePolicy(
            allowlisted_domains=set(
                config.get("allowlist", {}).get("domains", [])
            ),
            allowlisted_cidrs=set(
                config.get("allowlist", {}).get("cidrs", [])
            ),
            denylisted_domains=set(
                config.get("denylist", {}).get("domains", [])
            ),
            denylisted_cidrs=set(
                config.get("denylist", {}).get("cidrs", [])
            ),
            denylisted_patterns=set(
                config.get("denylist", {}).get("patterns", [])
            ),
        )

        engine = TargetPolicyEngine(policy)
        logger.info(
            f"Loaded target policy from {config_path}"
        )
        return engine

    except Exception as e:
        logger.error(f"Error loading policy config: {str(e)}")
        return TargetPolicyEngine()
