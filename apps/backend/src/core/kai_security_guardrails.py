"""
Kai Security Guardrails
Defensive authorization and audit controls for authorized vulnerability scanning
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib
import os
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class ToolRiskTier(Enum):
    """Risk classification for tools; informs approval gating."""
    TIER_0_SAFE = "tier_0_safe"        # passive / local only
    TIER_1_NOTIFY = "tier_1_notify"    # active-but-low-risk; notify only
    TIER_2_INTRUSIVE = "tier_2_intrusive"  # intrusive/exploit; approval required


# Minimal default policy; populated by adapters during registration.
TOOL_TIER_MAP: Dict[str, ToolRiskTier] = {}


def set_tool_tier(tool_id: str, tier: ToolRiskTier):
    """Register or update a tool's risk tier."""
    TOOL_TIER_MAP[tool_id] = tier


def get_tool_tier(tool_id: str) -> ToolRiskTier:
    """Resolve tier; default to intrusive if unknown to stay safe."""
    return TOOL_TIER_MAP.get(tool_id, ToolRiskTier.TIER_2_INTRUSIVE)


class ScanAuthorization(Enum):
    """Authorization types for scanning"""
    BUG_BOUNTY_PLATFORM = "bug_bounty_platform"  # HackerOne, Bugcrowd, etc.
    AUTHORIZED_ASSESSMENT = "authorized_assessment"  # Signed authorization
    INTERNAL_SECURITY = "internal_security"  # Internal security testing
    OSINT_ONLY = "osint_only"  # Public information gathering only


class ScanScope(Enum):
    """Scope restrictions for scans"""
    SINGLE_DOMAIN = "single_domain"
    DOMAIN_WILDCARD = "domain_wildcard"
    IP_RANGE = "ip_range"
    SPECIFIC_ENDPOINTS = "specific_endpoints"


@dataclass
class AuthorizationCertificate:
    """Certificate proving authorization for a scan"""
    certificate_id: str
    authorization_type: ScanAuthorization
    target: str  # Domain, IP range, or platform
    scope: ScanScope
    authorized_by: str  # Who authorized this
    issued_at: datetime
    expires_at: datetime
    allowed_methods: List[str]  # e.g., ["osint", "vulnerability_scanning", "web_testing"]
    metadata: Dict[str, Any]  # Platform-specific info, authorization documents
    signature: Optional[str] = None  # Cryptographic signature

    def is_valid(self) -> bool:
        """Check if certificate is still valid"""
        return datetime.utcnow() < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['authorization_type'] = self.authorization_type.value
        data['scope'] = self.scope.value
        data['issued_at'] = self.issued_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        return data


@dataclass
class ScanAuditLog:
    """Audit log entry for every scan operation"""
    log_id: str
    timestamp: datetime
    user_id: str
    certificate_id: str
    target: str
    scan_type: str  # "osint", "vulnerability_scan", "remediation"
    method: str  # Specific scanning method used
    status: str  # "started", "completed", "failed", "blocked"
    result_count: int = 0
    error_message: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class GuardRailEngine:
    """
    Enforces authorization and prevents misuse
    Ensures all scanning is authorized and properly logged
    """

    def __init__(self):
        self.authorized_certificates: Dict[str, AuthorizationCertificate] = {}
        self.audit_logs: List[ScanAuditLog] = []
        self.blocked_operations: List[Dict[str, Any]] = []
        self._lock = Lock()
        self.ledger_path = Path(
            os.getenv("K1_AUTH_LEDGER_PATH", "artifacts/auth/authorization_ledger.json")
        ).resolve()
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_ledger()

    def _load_ledger(self) -> None:
        """Load persisted certificates and decisions from disk."""
        if not self.ledger_path.exists():
            return
        try:
            payload = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to parse authorization ledger; starting fresh")
            return

        for cert_data in payload.get("certificates", []):
            cert = self._deserialize_certificate(cert_data)
            if cert:
                self.authorized_certificates[cert.certificate_id] = cert

        for log_data in payload.get("audit_logs", []):
            log = self._deserialize_audit_log(log_data)
            if log:
                self.audit_logs.append(log)

        self.blocked_operations = list(payload.get("blocked_operations", []))

    def _persist_ledger(self) -> None:
        """Persist certificates and decisions as append-only style state snapshots."""
        with self._lock:
            blocked = []
            for entry in self.blocked_operations:
                normalized = dict(entry)
                ts = normalized.get("timestamp")
                if isinstance(ts, datetime):
                    normalized["timestamp"] = ts.isoformat()
                blocked.append(normalized)
            payload = {
                "schema_version": "1.0",
                "updated_at": datetime.utcnow().isoformat(),
                "certificates": [cert.to_dict() for cert in self.authorized_certificates.values()],
                "audit_logs": [log.to_dict() for log in self.audit_logs],
                "blocked_operations": blocked,
            }
            self.ledger_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _deserialize_certificate(self, data: Dict[str, Any]) -> Optional[AuthorizationCertificate]:
        try:
            return AuthorizationCertificate(
                certificate_id=str(data["certificate_id"]),
                authorization_type=ScanAuthorization(str(data["authorization_type"])),
                target=str(data["target"]),
                scope=ScanScope(str(data["scope"])),
                authorized_by=str(data["authorized_by"]),
                issued_at=datetime.fromisoformat(str(data["issued_at"])),
                expires_at=datetime.fromisoformat(str(data["expires_at"])),
                allowed_methods=list(data.get("allowed_methods") or []),
                metadata=dict(data.get("metadata") or {}),
                signature=data.get("signature"),
            )
        except Exception:
            return None

    def _deserialize_audit_log(self, data: Dict[str, Any]) -> Optional[ScanAuditLog]:
        try:
            return ScanAuditLog(
                log_id=str(data["log_id"]),
                timestamp=datetime.fromisoformat(str(data["timestamp"])),
                user_id=str(data["user_id"]),
                certificate_id=str(data["certificate_id"]),
                target=str(data["target"]),
                scan_type=str(data["scan_type"]),
                method=str(data["method"]),
                status=str(data["status"]),
                result_count=int(data.get("result_count", 0)),
                error_message=data.get("error_message"),
                ip_address=data.get("ip_address"),
                user_agent=data.get("user_agent"),
                metadata=data.get("metadata"),
            )
        except Exception:
            return None

    def register_authorization(self, cert: AuthorizationCertificate) -> bool:
        """
        Register an authorization certificate
        Verifies the certificate before accepting it
        """
        logger.info(f"Registering authorization: {cert.certificate_id}")

        # Validation checks
        if not cert.is_valid():
            logger.error(f"Certificate expired: {cert.certificate_id}")
            return False

        if not self._validate_certificate_signature(cert):
            logger.error(f"Invalid certificate signature: {cert.certificate_id}")
            return False

        self.authorized_certificates[cert.certificate_id] = cert
        self._persist_ledger()
        logger.info(f"✅ Authorization registered: {cert.certificate_id}")
        return True

    def authorize_scan(
        self,
        user_id: str,
        target: str,
        scan_type: str,
        scan_method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[AuthorizationCertificate]]:
        """
        Check if a scan is authorized
        Returns: (authorized, reason, certificate)
        """
        logger.info(f"Authorizing scan: user={user_id}, target={target}, type={scan_type}")

        # Find matching authorization
        matching_cert = None
        for cert_id, cert in self.authorized_certificates.items():
            if self._matches_target(cert.target, target) and self._matches_method(
                cert.allowed_methods, scan_method
            ):
                if cert.is_valid():
                    matching_cert = cert
                    break

        if not matching_cert:
            reason = f"No valid authorization found for target: {target}"
            logger.warning(f"❌ Scan denied: {reason}")
            self._log_blocked_operation(
                user_id, target, scan_type, scan_method, reason, ip_address, user_agent
            )
            return False, reason, None

        # Check method is allowed
        if scan_method not in matching_cert.allowed_methods:
            reason = f"Method {scan_method} not authorized for this target"
            logger.warning(f"❌ Scan denied: {reason}")
            self._log_blocked_operation(
                user_id, target, scan_type, scan_method, reason, ip_address, user_agent
            )
            return False, reason, None

        logger.info(f"✅ Scan authorized: {matching_cert.certificate_id}")
        return True, None, matching_cert

    def log_scan_operation(
        self,
        user_id: str,
        certificate_id: str,
        target: str,
        scan_type: str,
        scan_method: str,
        status: str,
        result_count: int = 0,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        Log a scan operation for audit trail
        Returns: log_id
        """
        import uuid

        log_id = str(uuid.uuid4())
        log_entry = ScanAuditLog(
            log_id=log_id,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            certificate_id=certificate_id,
            target=target,
            scan_type=scan_type,
            method=scan_method,
            status=status,
            result_count=result_count,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.audit_logs.append(log_entry)
        self._persist_ledger()
        logger.info(f"📝 Audit logged: {log_id} - {status}")

        return log_id

    def get_audit_logs(
        self, user_id: Optional[str] = None, days: int = 30
    ) -> List[ScanAuditLog]:
        """Retrieve audit logs for compliance review"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        logs = [
            log
            for log in self.audit_logs
            if log.timestamp >= cutoff_date
            and (user_id is None or log.user_id == user_id)
        ]

        return logs

    def detect_suspicious_activity(self) -> List[Dict[str, Any]]:
        """
        Detect potentially malicious patterns
        - Multiple authorization denials from same user
        - Attempts to scan outside authorized scope
        - Rapid-fire scanning attempts
        """
        suspicious = []

        # Check for repeated authorization failures
        denied_operations = [op for op in self.blocked_operations]
        denied_by_user = {}

        for op in denied_operations:
            user = op.get("user_id")
            if user not in denied_by_user:
                denied_by_user[user] = 0
            denied_by_user[user] += 1

        for user, count in denied_by_user.items():
            if count > 10:  # More than 10 denied attempts
                suspicious.append(
                    {
                        "type": "repeated_authorization_failures",
                        "user_id": user,
                        "count": count,
                        "severity": "high",
                        "action": "Review user activity; consider rate limiting",
                    }
                )

        # Check for rapid-fire scans
        recent_logs = [log for log in self.audit_logs if log.timestamp > datetime.utcnow() - timedelta(minutes=5)]
        scans_by_user = {}
        for log in recent_logs:
            user = log.user_id
            if user not in scans_by_user:
                scans_by_user[user] = 0
            scans_by_user[user] += 1

        for user, count in scans_by_user.items():
            if count > 20:  # More than 20 scans in 5 minutes
                suspicious.append(
                    {
                        "type": "rapid_fire_scanning",
                        "user_id": user,
                        "count": count,
                        "severity": "medium",
                        "action": "Rate limit this user",
                    }
                )

        return suspicious

    def _matches_target(self, authorized_target: str, requested_target: str) -> bool:
        """Check if requested target matches authorization"""
        if authorized_target == requested_target:
            return True

        # Support wildcards like *.example.com
        # Use dot-boundary check to prevent *.example.com matching evilexample.com.
        if authorized_target.startswith("*."):
            domain_part = authorized_target[2:]  # Remove "*."
            if requested_target == domain_part or requested_target.endswith("." + domain_part):
                return True

        return False

    def _matches_method(self, allowed_methods: List[str], requested_method: str) -> bool:
        """Check if requested method is allowed"""
        return requested_method in allowed_methods

    def _validate_certificate_signature(self, cert: AuthorizationCertificate) -> bool:
        """Validate cryptographic signature of certificate"""
        logger.debug(f"Validating certificate: {cert.certificate_id}")
        if not cert.signature:
            # Default to False — unsigned certificates are rejected unless
            # K1_ALLOW_UNSIGNED_CERTIFICATES=true is explicitly set.
            return _env_bool("K1_ALLOW_UNSIGNED_CERTIFICATES", False)

        signing_key = (os.getenv("K1_AUTH_CERT_SIGNING_KEY") or "").strip()
        if not signing_key:
            # No signing key configured — cannot verify. Reject by default.
            return _env_bool("K1_ALLOW_UNSIGNED_CERTIFICATES", False)

        canonical = "|".join(
            [
                cert.certificate_id,
                cert.target,
                cert.authorized_by,
                cert.issued_at.isoformat(),
                cert.expires_at.isoformat(),
                ",".join(sorted(cert.allowed_methods)),
            ]
        )
        expected = hashlib.sha256(f"{canonical}|{signing_key}".encode("utf-8")).hexdigest()
        return cert.signature == expected

    def _log_blocked_operation(
        self,
        user_id: str,
        target: str,
        scan_type: str,
        scan_method: str,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log a blocked/denied operation"""
        self.blocked_operations.append(
            {
                "timestamp": datetime.utcnow(),
                "user_id": user_id,
                "target": target,
                "scan_type": scan_type,
                "scan_method": scan_method,
                "reason": reason,
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
        )
        self._persist_ledger()

    def get_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        return {
            "total_authorizations": len(self.authorized_certificates),
            "active_authorizations": sum(
                1 for cert in self.authorized_certificates.values() if cert.is_valid()
            ),
            "total_audit_logs": len(self.audit_logs),
            "blocked_operations": len(self.blocked_operations),
            "suspicious_activities": len(self.detect_suspicious_activity()),
        }


# Global guard rail engine instance
_global_guardrail_engine = GuardRailEngine()


def get_guardrail_engine() -> GuardRailEngine:
    """Get the global guard rail engine"""
    return _global_guardrail_engine
