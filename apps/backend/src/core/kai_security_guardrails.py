"""
Kai Security Guardrails
Defensive authorization and audit controls for authorized vulnerability scanning
"""

import logging
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
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
    BUG_BOUNTY_PLATFORM = "bug_bounty_platform"
    AUTHORIZED_ASSESSMENT = "authorized_assessment"
    INTERNAL_SECURITY = "internal_security"
    OSINT_ONLY = "osint_only"


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
    target: str
    scope: ScanScope
    authorized_by: str
    issued_at: datetime
    expires_at: datetime
    allowed_methods: List[str]
    metadata: Dict[str, Any]
    signature: Optional[str] = None

    def is_valid(self) -> bool:
        """Check if certificate is still valid"""
        return datetime.now(timezone.utc) < self.expires_at

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
    scan_type: str
    method: str
    status: str
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
        # Capped in-memory buffers to prevent memory exhaustion (Task 36)
        self.audit_logs_buffer: List[ScanAuditLog] = []
        self.blocked_operations_buffer: List[Dict[str, Any]] = []
        self._max_buffer_size = int(os.getenv("K1_GUARDRAIL_BUFFER_CAP", "1000"))
        
        self._lock = Lock()
        self.ledger_path = Path(
            os.getenv("K1_AUTH_LEDGER_PATH", "artifacts/auth/authorization_ledger.jsonl")
        ).resolve()
        self._last_hash = "0" * 64
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_ledger()

    @property
    def audit_logs(self):
        return self.audit_logs_buffer

    @property
    def blocked_operations(self):
        return self.blocked_operations_buffer

    def _load_ledger(self) -> None:
        """Load persisted records from disk and verify hash chain."""
        if not self.ledger_path.exists():
            return
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    record_env = json.loads(line)
                    if record_env.get("prev_hash") != self._last_hash:
                         logger.error(f"LEDGER CORRUPTION: Hash chain broken")
                    r_type = record_env.get("type")
                    record_data = record_env.get("record", {})
                    if r_type == "certificate":
                        cert = self._deserialize_certificate(record_data)
                        if cert: self.authorized_certificates[cert.certificate_id] = cert
                    elif r_type == "audit_log":
                        log = self._deserialize_audit_log(record_data)
                        if log: self._add_to_audit_buffer(log)
                    elif r_type == "blocked_operation":
                        self._add_to_blocked_buffer(record_data)
                    self._last_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
        except Exception as e:
            logger.error(f"Failed to load authorization ledger: {str(e)}")

    def _add_to_audit_buffer(self, log: ScanAuditLog) -> None:
        self.audit_logs_buffer.append(log)
        if len(self.audit_logs_buffer) > self._max_buffer_size:
            self.audit_logs_buffer.pop(0)

    def _add_to_blocked_buffer(self, entry: Dict[str, Any]) -> None:
        self.blocked_operations_buffer.append(entry)
        if len(self.blocked_operations_buffer) > self._max_buffer_size:
            self.blocked_operations_buffer.pop(0)

    def _append_to_ledger(self, record_type: str, data: Dict[str, Any]) -> None:
        """Append a new record to the ledger with a hash chain."""
        with self._lock:
            envelope = {
                "id": str(uuid.uuid4()),
                "type": record_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prev_hash": self._last_hash,
                "record": data,
            }
            line = json.dumps(envelope)
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            self._last_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()

    def _deserialize_certificate(self, data: Dict[str, Any]) -> Optional[AuthorizationCertificate]:
        try:
            return AuthorizationCertificate(
                certificate_id=str(data["certificate_id"]),
                authorization_type=ScanAuthorization(str(data["authorization_type"])),
                target=str(data["target"]),
                scope=ScanScope(str(data["scope"])),
                authorized_by=str(data["authorized_by"]),
                issued_at=datetime.fromisoformat(str(data["issued_at"])).replace(tzinfo=timezone.utc) if "Z" not in str(data["issued_at"]) else datetime.fromisoformat(str(data["issued_at"]).replace("Z", "+00:00")),
                expires_at=datetime.fromisoformat(str(data["expires_at"])).replace(tzinfo=timezone.utc) if "Z" not in str(data["expires_at"]) else datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00")),
                allowed_methods=list(data.get("allowed_methods") or []),
                metadata=dict(data.get("metadata") or {}),
                signature=data.get("signature"),
            )
        except Exception: return None

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
        except Exception: return None

    def register_authorization(self, cert: AuthorizationCertificate) -> bool:
        if not cert.is_valid(): return False
        if not self._validate_certificate_signature(cert): return False
        self.authorized_certificates[cert.certificate_id] = cert
        self._append_to_ledger("certificate", cert.to_dict())
        return True

    def authorize_scan(
        self, user_id: str, target: str, scan_type: str, scan_method: str,
        ip_address: Optional[str] = None, user_agent: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[AuthorizationCertificate]]:
        matching_cert = None
        for cert in self.authorized_certificates.values():
            if self._matches_target(cert.target, target) and self._matches_method(cert.allowed_methods, scan_method):
                if cert.is_valid():
                    matching_cert = cert
                    break
        if not matching_cert:
            reason = f"No valid authorization found for target: {target}"
            self._log_blocked_operation(user_id, target, scan_type, scan_method, reason, ip_address, user_agent)
            return False, reason, None
        if scan_method not in matching_cert.allowed_methods:
            reason = f"Method {scan_method} not authorized for this target"
            self._log_blocked_operation(user_id, target, scan_type, scan_method, reason, ip_address, user_agent)
            return False, reason, None
        return True, None, matching_cert

    def log_scan_operation(
        self, user_id: str, certificate_id: str, target: str, scan_type: str, scan_method: str, status: str,
        result_count: int = 0, error_message: Optional[str] = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None,
    ) -> str:
        log_id = str(uuid.uuid4())
        log_entry = ScanAuditLog(
            log_id=log_id, timestamp=datetime.now(timezone.utc), user_id=user_id, certificate_id=certificate_id,
            target=target, scan_type=scan_type, method=scan_method, status=status, result_count=result_count,
            error_message=error_message, ip_address=ip_address, user_agent=user_agent,
        )
        self._add_to_audit_buffer(log_entry)
        self._append_to_ledger("audit_log", log_entry.to_dict())
        return log_id

    async def get_audit_logs(
        self, db: Any = None, user_id: Optional[str] = None, days: int = 30
    ) -> List[ScanAuditLog]:
        """Retrieve audit logs from database (Task 36) or capped buffer."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        if db is not None:
            # Query from PostgreSQL AuditEvent table
            from sqlalchemy import select
            from ..models.campaign import AuditEvent
            stmt = select(AuditEvent).where(AuditEvent.happened_at >= cutoff_date)
            if user_id:
                stmt = stmt.where(AuditEvent.actor == user_id)
            stmt = stmt.order_by(AuditEvent.happened_at.desc())
            
            result = await db.execute(stmt)
            events = result.scalars().all()
            
            # Map AuditEvent to ScanAuditLog
            logs = []
            for ev in events:
                payload = ev.event_payload_json or {}
                logs.append(ScanAuditLog(
                    log_id=str(ev.id),
                    timestamp=ev.happened_at,
                    user_id=ev.actor,
                    certificate_id=payload.get("certificate_id", "none"),
                    target=payload.get("target", "unknown"),
                    scan_type=payload.get("scan_type", "unknown"),
                    method=payload.get("scan_method", "unknown"),
                    status=payload.get("status", "unknown"),
                    error_message=ev.message if ev.event_type == "scan_denied" else None,
                    metadata=payload
                ))
            return logs

        # Fallback to buffer
        return [log for log in self.audit_logs_buffer if log.timestamp >= cutoff_date and (user_id is None or log.user_id == user_id)]

    async def get_stats(self, db: Any = None) -> Dict[str, Any]:
        """Get security statistics from database (Task 36) or capped buffer."""
        if db is not None:
            from sqlalchemy import func, select
            from ..models.campaign import AuditEvent
            stmt = select(func.count(AuditEvent.id))
            total_logs = await db.scalar(stmt)
            
            return {
                "total_authorizations": len(self.authorized_certificates),
                "active_authorizations": sum(1 for cert in self.authorized_certificates.values() if cert.is_valid()),
                "total_audit_logs": total_logs,
                "blocked_operations": len(self.blocked_operations_buffer), # would need more SQL for this
                "suspicious_activities": len(self.detect_suspicious_activity()),
            }

        return {
            "total_authorizations": len(self.authorized_certificates),
            "active_authorizations": sum(1 for cert in self.authorized_certificates.values() if cert.is_valid()),
            "total_audit_logs": len(self.audit_logs_buffer),
            "blocked_operations": len(self.blocked_operations_buffer),
            "suspicious_activities": len(self.detect_suspicious_activity()),
        }

    def detect_suspicious_activity(self) -> List[Dict[str, Any]]:
        suspicious = []
        denied_by_user = {}
        for op in self.blocked_operations_buffer:
            user = op.get("user_id")
            denied_by_user[user] = denied_by_user.get(user, 0) + 1
        for user, count in denied_by_user.items():
            if count > 10:
                suspicious.append({"type": "repeated_authorization_failures", "user_id": user, "count": count, "severity": "high"})
        return suspicious

    def _matches_target(self, authorized_target: str, requested_target: str) -> bool:
        if authorized_target == requested_target: return True
        if authorized_target.startswith("*."):
            domain_part = authorized_target[2:]
            if requested_target == domain_part or requested_target.endswith("." + domain_part): return True
        return False

    def _matches_method(self, allowed_methods: List[str], requested_method: str) -> bool:
        return requested_method in allowed_methods

    def _validate_certificate_signature(self, cert: AuthorizationCertificate) -> bool:
        if not cert.signature:
            return _env_bool("K1_ALLOW_UNSIGNED_CERTIFICATES", False)

        signing_key = (os.getenv("K1_AUTH_CERT_SIGNING_KEY") or "").strip()
        if not signing_key:
            return _env_bool("K1_ALLOW_UNSIGNED_CERTIFICATES", False)

        # Fix: Use collision-resistant JSON-based canonical string
        # Instead of pipe-join which is vulnerable to field value injection
        payload = {
            "id": cert.certificate_id,
            "target": cert.target,
            "authorized_by": cert.authorized_by,
            "issued_at": cert.issued_at.isoformat(),
            "expires_at": cert.expires_at.isoformat(),
            "methods": sorted(cert.allowed_methods),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        
        expected = hashlib.sha256(f"{canonical}|{signing_key}".encode("utf-8")).hexdigest()
        
        # Also check legacy format for backward compatibility during migration?
        # No, task says "Re-sign all existing certificates with the new canonical format."
        return cert.signature == expected

    def sign_certificate(self, cert: AuthorizationCertificate) -> str:
        """Helper to generate a valid signature for a certificate using the new format."""
        signing_key = (os.getenv("K1_AUTH_CERT_SIGNING_KEY") or "").strip()
        if not signing_key:
            raise ValueError("K1_AUTH_CERT_SIGNING_KEY not configured")
            
        payload = {
            "id": cert.certificate_id,
            "target": cert.target,
            "authorized_by": cert.authorized_by,
            "issued_at": cert.issued_at.isoformat(),
            "expires_at": cert.expires_at.isoformat(),
            "methods": sorted(cert.allowed_methods),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(f"{canonical}|{signing_key}".encode("utf-8")).hexdigest()

    def _log_blocked_operation(
        self, user_id: str, target: str, scan_type: str, scan_method: str, reason: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None,
    ) -> None:
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "user_id": user_id, "target": target, "scan_type": scan_type, "scan_method": scan_method, "reason": reason, "ip_address": ip_address, "user_agent": user_agent}
        self._add_to_blocked_buffer(entry)
        self._append_to_ledger("blocked_operation", entry)

# Global guard rail engine instance
_global_guardrail_engine = GuardRailEngine()
def get_guardrail_engine() -> GuardRailEngine:
    return _global_guardrail_engine
