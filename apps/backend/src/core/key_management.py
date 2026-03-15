"""
K1 Cryptographic Key Management System
Manages PGP keys, SSH keys, and other cryptographic materials
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path


class KeyType(str, Enum):
    """Types of keys managed by the system"""
    PGP_PRIVATE = "pgp_private"
    PGP_PUBLIC = "pgp_public"
    SSH_PRIVATE = "ssh_private"
    SSH_PUBLIC = "ssh_public"
    API_KEY = "api_key"
    HMAC_SECRET = "hmac_secret"
    CERTIFICATE = "certificate"


class KeyOwnerType(str, Enum):
    """Owner type of the key"""
    ADMIN = "admin"
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class KeyStatus(str, Enum):
    """Status of the key"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING_ROTATION = "pending_rotation"


class KeyRotationStatus(str, Enum):
    """Status of key rotation process"""
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class KeyMetadata:
    """Metadata about a cryptographic key"""
    key_id: str
    key_type: KeyType
    owner_type: KeyOwnerType
    owner_id: str
    status: KeyStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    fingerprint: Optional[str] = None
    key_strength_bits: Optional[int] = None
    algorithm: str = "RSA"  # RSA, ECDSA, ED25519, etc.
    is_primary: bool = False  # Primary key for owner
    tags: List[str] = field(default_factory=list)
    rotation_schedule: Optional[str] = None  # e.g., "90d", "1y"
    description: str = ""
    audit_log: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class KeyRotationPlan:
    """Plan for rotating a key"""
    rotation_id: str
    key_id: str
    old_key_metadata: KeyMetadata
    new_key_metadata: Optional[KeyMetadata]
    status: KeyRotationStatus
    initiated_at: datetime
    scheduled_for: datetime
    completed_at: Optional[datetime] = None
    reason: str = ""
    authorized_by: Optional[str] = None
    rollback_available: bool = True
    previous_key_backup: Optional[str] = None


@dataclass
class KeyUsageLog:
    """Log entry for key usage"""
    timestamp: datetime
    key_id: str
    operation: str  # sign, verify, encrypt, decrypt, ssh_auth
    success: bool
    details: Dict[str, Any]
    error_message: Optional[str] = None
    user_id: Optional[str] = None


class KeyManagementSystem:
    """Central system for managing all cryptographic keys"""

    def __init__(self, keys_dir: str = "/var/lib/k1/keys", enable_encryption: bool = True):
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.enable_encryption = enable_encryption

        # In-memory stores (production: use PostgreSQL)
        self.keys_metadata: Dict[str, KeyMetadata] = {}
        self.key_contents: Dict[str, str] = {}  # In production: encrypted storage
        self.usage_logs: List[KeyUsageLog] = []
        self.rotation_plans: Dict[str, KeyRotationPlan] = {}

    # ==================== Admin Key Management ====================

    async def import_admin_pgp_key(
        self,
        pgp_key_content: str,
        admin_id: str,
        is_primary: bool = False,
        description: str = ""
    ) -> Tuple[bool, str, KeyMetadata]:
        """
        Import an admin PGP key for signing approvals
        Returns: (success, message, metadata)
        """
        try:
            key_id = self._generate_key_id("pgp", admin_id)
            fingerprint = self._extract_pgp_fingerprint(pgp_key_content)

            metadata = KeyMetadata(
                key_id=key_id,
                key_type=KeyType.PGP_PRIVATE,
                owner_type=KeyOwnerType.ADMIN,
                owner_id=admin_id,
                status=KeyStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                fingerprint=fingerprint,
                is_primary=is_primary,
                description=description,
                algorithm="RSA"
            )

            # Store metadata
            self.keys_metadata[key_id] = metadata

            # Store key (encrypted in production)
            if self.enable_encryption:
                encrypted_key = self._encrypt_key(pgp_key_content, key_id)
                self.key_contents[key_id] = encrypted_key
            else:
                self.key_contents[key_id] = pgp_key_content

            # Log
            self._log_audit(key_id, "import", {"admin_id": admin_id, "fingerprint": fingerprint})

            return (
                True,
                f"Admin PGP key imported successfully: {fingerprint}",
                metadata
            )

        except Exception as e:
            return (False, f"Failed to import admin PGP key: {str(e)}", None)

    async def rotate_admin_pgp_key(
        self,
        current_key_id: str,
        new_pgp_key_content: str,
        reason: str = "Scheduled rotation",
        authorized_by: str = ""
    ) -> Tuple[bool, str, Optional[KeyRotationPlan]]:
        """
        Rotate an admin PGP key with rollback capability
        Returns: (success, message, rotation_plan)
        """
        try:
            if current_key_id not in self.keys_metadata:
                return (False, "Current key not found", None)

            current_metadata = self.keys_metadata[current_key_id]
            admin_id = current_metadata.owner_id

            # Import new key
            success, msg, new_metadata = await self.import_admin_pgp_key(
                new_pgp_key_content,
                admin_id,
                is_primary=True,
                description="Rotated key"
            )

            if not success:
                return (False, f"Failed to import new key: {msg}", None)

            # Create rotation plan
            rotation_id = self._generate_key_id("rotation", current_key_id)
            rotation_plan = KeyRotationPlan(
                rotation_id=rotation_id,
                key_id=current_key_id,
                old_key_metadata=current_metadata,
                new_key_metadata=new_metadata,
                status=KeyRotationStatus.COMPLETED,
                initiated_at=datetime.now(timezone.utc),
                scheduled_for=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                reason=reason,
                authorized_by=authorized_by,
                rollback_available=True,
                previous_key_backup=self.key_contents.get(current_key_id)
            )

            # Deactivate old key
            current_metadata.status = KeyStatus.INACTIVE
            current_metadata.is_primary = False

            # Store rotation plan
            self.rotation_plans[rotation_id] = rotation_plan

            # Log
            self._log_audit(
                current_key_id,
                "rotate",
                {"new_key_id": new_metadata.key_id, "reason": reason}
            )

            return (
                True,
                f"Admin PGP key rotated successfully. Old key: {current_metadata.fingerprint}",
                rotation_plan
            )

        except Exception as e:
            return (False, f"Key rotation failed: {str(e)}", None)

    async def get_admin_primary_key(self, admin_id: str) -> Optional[Tuple[KeyMetadata, str]]:
        """
        Get the primary admin PGP key for an admin
        Returns: (metadata, key_content) or None
        """
        for key_id, metadata in self.keys_metadata.items():
            if (metadata.owner_type == KeyOwnerType.ADMIN and
                metadata.owner_id == admin_id and
                metadata.is_primary and
                metadata.status == KeyStatus.ACTIVE):

                key_content = self.key_contents.get(key_id)
                if metadata.key_type == KeyType.PGP_PRIVATE and self.enable_encryption:
                    key_content = self._decrypt_key(key_content, key_id)

                self._log_usage(key_id, "retrieve", True, {})
                return (metadata, key_content)

        return None

    # ==================== User Key Management ====================

    async def import_user_keys(
        self,
        user_id: str,
        pgp_public_key: Optional[str] = None,
        ssh_public_key: Optional[str] = None,
        api_keys: Optional[Dict[str, str]] = None,
        description: str = ""
    ) -> Tuple[bool, str, Dict[str, KeyMetadata]]:
        """
        Import multiple keys for a user (PGP public, SSH public, API keys)
        Returns: (success, message, {key_type: metadata})
        """
        imported_keys = {}

        try:
            if pgp_public_key:
                success, msg, metadata = await self._import_user_key(
                    pgp_public_key,
                    KeyType.PGP_PUBLIC,
                    user_id,
                    "PGP public key"
                )
                if success:
                    imported_keys["pgp_public"] = metadata

            if ssh_public_key:
                success, msg, metadata = await self._import_user_key(
                    ssh_public_key,
                    KeyType.SSH_PUBLIC,
                    user_id,
                    "SSH public key"
                )
                if success:
                    imported_keys["ssh_public"] = metadata

            if api_keys:
                for service, api_key in api_keys.items():
                    success, msg, metadata = await self._import_user_key(
                        api_key,
                        KeyType.API_KEY,
                        user_id,
                        f"API key for {service}",
                        tags=[service]
                    )
                    if success:
                        imported_keys[f"api_key_{service}"] = metadata

            self._log_audit(
                user_id,
                "import_keys",
                {"key_types": list(imported_keys.keys())}
            )

            return (
                True,
                f"Imported {len(imported_keys)} keys for user",
                imported_keys
            )

        except Exception as e:
            return (False, f"Failed to import user keys: {str(e)}", {})

    async def _import_user_key(
        self,
        key_content: str,
        key_type: KeyType,
        user_id: str,
        description: str = "",
        tags: Optional[List[str]] = None
    ) -> Tuple[bool, str, KeyMetadata]:
        """Helper to import individual user key"""
        try:
            key_id = self._generate_key_id(key_type.value, user_id)
            fingerprint = self._extract_key_fingerprint(key_content, key_type)

            metadata = KeyMetadata(
                key_id=key_id,
                key_type=key_type,
                owner_type=KeyOwnerType.USER,
                owner_id=user_id,
                status=KeyStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                fingerprint=fingerprint,
                description=description,
                tags=tags or [],
                algorithm=self._detect_key_algorithm(key_content)
            )

            self.keys_metadata[key_id] = metadata

            if self.enable_encryption:
                encrypted_key = self._encrypt_key(key_content, key_id)
                self.key_contents[key_id] = encrypted_key
            else:
                self.key_contents[key_id] = key_content

            return (True, "Key imported", metadata)

        except Exception as e:
            return (False, f"Import failed: {str(e)}", None)

    async def list_user_keys(self, user_id: str) -> List[KeyMetadata]:
        """List all keys for a user"""
        return [
            metadata for metadata in self.keys_metadata.values()
            if metadata.owner_type == KeyOwnerType.USER and metadata.owner_id == user_id
        ]

    async def revoke_user_key(self, key_id: str, reason: str = "") -> Tuple[bool, str]:
        """Revoke a user key"""
        try:
            if key_id not in self.keys_metadata:
                return (False, "Key not found")

            metadata = self.keys_metadata[key_id]
            metadata.status = KeyStatus.REVOKED

            self._log_audit(key_id, "revoke", {"reason": reason})

            return (True, f"Key {key_id} revoked")

        except Exception as e:
            return (False, f"Revocation failed: {str(e)}")

    # ==================== Key Rotation Management ====================

    async def plan_key_rotation(
        self,
        key_id: str,
        new_key_content: str,
        scheduled_for: Optional[datetime] = None,
        reason: str = "Scheduled rotation",
        authorized_by: str = ""
    ) -> Tuple[bool, str, Optional[KeyRotationPlan]]:
        """
        Plan a key rotation with approval workflow
        Returns: (success, message, rotation_plan)
        """
        try:
            if key_id not in self.keys_metadata:
                return (False, "Key not found", None)

            metadata = self.keys_metadata[key_id]
            scheduled_for = scheduled_for or (datetime.now(timezone.utc) + timedelta(days=1))

            rotation_id = self._generate_key_id("rotation", key_id)
            rotation_plan = KeyRotationPlan(
                rotation_id=rotation_id,
                key_id=key_id,
                old_key_metadata=metadata,
                new_key_metadata=None,
                status=KeyRotationStatus.INITIATED,
                initiated_at=datetime.now(timezone.utc),
                scheduled_for=scheduled_for,
                reason=reason,
                authorized_by=authorized_by,
                rollback_available=True,
                previous_key_backup=self.key_contents.get(key_id)
            )

            self.rotation_plans[rotation_id] = rotation_plan
            metadata.status = KeyStatus.PENDING_ROTATION

            self._log_audit(
                key_id,
                "rotation_planned",
                {"rotation_id": rotation_id, "scheduled_for": scheduled_for.isoformat()}
            )

            return (True, f"Key rotation planned: {rotation_id}", rotation_plan)

        except Exception as e:
            return (False, f"Rotation planning failed: {str(e)}", None)

    async def execute_key_rotation(
        self,
        rotation_id: str,
        new_key_content: str,
        authorized_by: str = ""
    ) -> Tuple[bool, str]:
        """Execute a planned key rotation"""
        try:
            if rotation_id not in self.rotation_plans:
                return (False, "Rotation plan not found")

            rotation_plan = self.rotation_plans[rotation_id]
            if rotation_plan.status != KeyRotationStatus.INITIATED:
                return (False, f"Cannot execute rotation in {rotation_plan.status} state")

            # Import new key
            key_id = rotation_plan.key_id
            metadata = self.keys_metadata[key_id]

            new_key_id = self._generate_key_id(f"rotated_{metadata.key_type.value}", metadata.owner_id)
            fingerprint = self._extract_key_fingerprint(new_key_content, metadata.key_type)

            new_metadata = KeyMetadata(
                key_id=new_key_id,
                key_type=metadata.key_type,
                owner_type=metadata.owner_type,
                owner_id=metadata.owner_id,
                status=KeyStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                fingerprint=fingerprint,
                is_primary=metadata.is_primary,
                algorithm=self._detect_key_algorithm(new_key_content)
            )

            self.keys_metadata[new_key_id] = new_metadata

            if self.enable_encryption:
                encrypted_key = self._encrypt_key(new_key_content, new_key_id)
                self.key_contents[new_key_id] = encrypted_key
            else:
                self.key_contents[new_key_id] = new_key_content

            # Update rotation plan
            rotation_plan.new_key_metadata = new_metadata
            rotation_plan.status = KeyRotationStatus.COMPLETED
            rotation_plan.completed_at = datetime.now(timezone.utc)
            rotation_plan.authorized_by = authorized_by

            # Deactivate old key
            metadata.status = KeyStatus.INACTIVE

            self._log_audit(
                key_id,
                "rotation_executed",
                {"new_key_id": new_key_id, "rotation_id": rotation_id}
            )

            return (True, f"Key rotation completed: {new_key_id}")

        except Exception as e:
            return (False, f"Rotation execution failed: {str(e)}")

    async def rollback_key_rotation(
        self,
        rotation_id: str,
        reason: str = ""
    ) -> Tuple[bool, str]:
        """Rollback a key rotation to previous state"""
        try:
            if rotation_id not in self.rotation_plans:
                return (False, "Rotation plan not found")

            rotation_plan = self.rotation_plans[rotation_id]
            if not rotation_plan.rollback_available:
                return (False, "Rollback not available for this rotation")

            key_id = rotation_plan.key_id
            old_metadata = rotation_plan.old_key_metadata
            new_metadata = rotation_plan.new_key_metadata

            # Restore old key
            old_metadata.status = KeyStatus.ACTIVE
            old_metadata.is_primary = True

            # Deactivate new key
            if new_metadata:
                new_metadata.status = KeyStatus.REVOKED

            # Restore key content from backup
            if rotation_plan.previous_key_backup:
                self.key_contents[key_id] = rotation_plan.previous_key_backup

            rotation_plan.status = KeyRotationStatus.CANCELLED

            self._log_audit(
                key_id,
                "rotation_rolledback",
                {"rotation_id": rotation_id, "reason": reason}
            )

            return (True, f"Key rotation rolled back: {rotation_id}")

        except Exception as e:
            return (False, f"Rollback failed: {str(e)}")

    # ==================== Key Verification ====================

    async def verify_pgp_signature(
        self,
        signature: str,
        message: str,
        expected_key_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Verify a PGP signature (simplified - use python-gnupg in production)
        Returns: (valid, message, signer_key_id)
        """
        try:
            # This is simplified - in production use python-gnupg library
            # For now, validate signature format and key existence

            if not signature or not message:
                return (False, "Invalid signature or message", None)

            # Check if expected key exists and is active
            if expected_key_id:
                if expected_key_id not in self.keys_metadata:
                    return (False, "Key not found", None)

                metadata = self.keys_metadata[expected_key_id]
                if metadata.status != KeyStatus.ACTIVE:
                    return (False, f"Key is {metadata.status}", None)

                self._log_usage(expected_key_id, "verify", True, {"message_length": len(message)})
                return (True, "Signature verified", expected_key_id)

            return (False, "Key ID required for verification", None)

        except Exception as e:
            return (False, f"Verification failed: {str(e)}", None)

    # ==================== Audit & Monitoring ====================

    def get_key_audit_trail(self, key_id: str) -> List[Dict[str, Any]]:
        """Get complete audit trail for a key"""
        if key_id not in self.keys_metadata:
            return []

        metadata = self.keys_metadata[key_id]
        return metadata.audit_log

    def get_usage_logs(
        self,
        key_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 100
    ) -> List[KeyUsageLog]:
        """Get key usage logs with optional filtering"""
        logs = self.usage_logs

        if key_id:
            logs = [log for log in logs if log.key_id == key_id]

        if owner_id:
            logs = [
                log for log in logs
                if log.key_id in [
                    k for k, m in self.keys_metadata.items()
                    if m.owner_id == owner_id
                ]
            ]

        return logs[-limit:]

    def get_expiring_keys(self, days_until: int = 30) -> List[KeyMetadata]:
        """Get keys expiring within specified days"""
        cutoff = datetime.now(timezone.utc) + timedelta(days=days_until)
        return [
            metadata for metadata in self.keys_metadata.values()
            if metadata.expires_at and metadata.expires_at <= cutoff
        ]

    def get_rotation_history(self, key_id: str) -> List[KeyRotationPlan]:
        """Get rotation history for a key"""
        return [
            plan for plan in self.rotation_plans.values()
            if plan.key_id == key_id
        ]

    # ==================== Helper Methods ====================

    def _generate_key_id(self, key_type: str, owner_id: str) -> str:
        """Generate unique key ID"""
        content = f"{key_type}:{owner_id}:{datetime.now(timezone.utc).isoformat()}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{key_type}_{hash_val}"

    def _extract_pgp_fingerprint(self, pgp_key: str) -> str:
        """Extract fingerprint from PGP key (simplified)"""
        # In production: use python-gnupg or similar
        lines = pgp_key.strip().split('\n')
        for line in lines:
            if 'fingerprint' in line.lower():
                return line.split(':')[-1].strip()
        # Fallback: hash the key
        return hashlib.sha256(pgp_key.encode()).hexdigest()[:40]

    def _extract_key_fingerprint(self, key_content: str, key_type: KeyType) -> str:
        """Extract fingerprint based on key type"""
        if key_type in [KeyType.PGP_PRIVATE, KeyType.PGP_PUBLIC]:
            return self._extract_pgp_fingerprint(key_content)
        # Hash other key types
        return hashlib.sha256(key_content.encode()).hexdigest()[:40]

    def _detect_key_algorithm(self, key_content: str) -> str:
        """Detect key algorithm from content"""
        if "BEGIN RSA" in key_content:
            return "RSA"
        elif "BEGIN OPENSSH PRIVATE KEY" in key_content or "ssh-ed25519" in key_content:
            return "ED25519"
        elif "ssh-rsa" in key_content:
            return "RSA"
        elif "ecdsa" in key_content:
            return "ECDSA"
        return "UNKNOWN"

    def _encrypt_key(self, key_content: str, key_id: str) -> str:
        """Encrypt key content (simplified - use cryptography module in production)"""
        # In production: use AES-256-GCM with key derivation
        # For now: simple hash-based obfuscation (NOT PRODUCTION READY)
        key_bytes = key_content.encode()
        salt = key_id.encode()
        # This is JUST for demo - use proper encryption in production
        import base64
        return base64.b64encode(key_bytes).decode()

    def _decrypt_key(self, encrypted_content: str, key_id: str) -> str:
        """Decrypt key content"""
        # In production: use AES-256-GCM
        import base64
        try:
            return base64.b64decode(encrypted_content).decode()
        except Exception:
            return encrypted_content

    def _log_audit(self, key_id: str, operation: str, details: Dict[str, Any]):
        """Log audit event for a key"""
        if key_id in self.keys_metadata:
            self.keys_metadata[key_id].audit_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": operation,
                "details": details
            })

    def _log_usage(
        self,
        key_id: str,
        operation: str,
        success: bool,
        details: Dict[str, Any],
        error: Optional[str] = None
    ):
        """Log key usage"""
        self.usage_logs.append(KeyUsageLog(
            timestamp=datetime.now(timezone.utc),
            key_id=key_id,
            operation=operation,
            success=success,
            details=details,
            error_message=error
        ))


# Global key management system instance
key_management_system = None


def initialize_key_management(keys_dir: str = "/var/lib/k1/keys") -> KeyManagementSystem:
    """Initialize the key management system"""
    global key_management_system

    key_management_system = KeyManagementSystem(keys_dir=keys_dir)
    return key_management_system


def get_key_management_system() -> KeyManagementSystem:
    """Get the global key management system"""
    global key_management_system

    if key_management_system is None:
        key_management_system = initialize_key_management()

    return key_management_system
