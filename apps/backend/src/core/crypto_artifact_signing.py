"""
Kai Cryptographic Artifact Signing & Chain of Custody
Handles automated signing and verification of vulnerability reports and scan logs
using PGP infrastructure for tamper detection and audit trails
"""

import gnupg
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib


class VerificationStatus(str, Enum):
    """Signature verification results"""
    VALID = "valid"
    INVALID = "invalid"
    TAMPERED = "tampered"
    UNSIGNED = "unsigned"
    UNTRUSTED = "untrusted"


@dataclass
class SignatureRecord:
    """Record of a signature operation"""
    artifact_path: str
    signature_path: str
    signer_identity: str
    signer_fingerprint: str
    signed_at: datetime
    algorithm: str
    artifact_hash: str  # SHA256 of artifact
    signature_valid: bool


@dataclass
class VerificationRecord:
    """Record of a verification operation"""
    artifact_path: str
    signature_path: str
    verified_at: datetime
    status: VerificationStatus
    signer_identity: str
    signer_fingerprint: str
    tamper_detected: bool
    details: Dict[str, Any]


class KaiCryptoSystem:
    """
    Secure cryptographic artifact signing and verification system
    Implements chain of custody for vulnerability reports and scan logs
    """

    def __init__(
        self,
        gpg_home: str = None,
        key_source_dir: str = None,
        machine_identity: str = "machine-kaisonai@pm.me"
    ):
        """
        Initialize the crypto system

        Args:
            gpg_home: Path to GnuPG home directory (default: ~/.kai/gpg_home)
            key_source_dir: Path to Kai PGP-Keys directory (default: /home/user/kai/Kai PGP-Keys)
            machine_identity: The machine signing identity (default: machine-kaisonai@pm.me)
        """
        self.gpg_home = Path(gpg_home or os.path.expanduser("~/.kai/gpg_home"))
        self.key_source_dir = Path(key_source_dir or "/home/user/kai/Kai PGP-Keys")
        self.machine_identity = machine_identity

        # Ensure GPG home exists with strict permissions
        self.gpg_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.gpg_home, 0o700)

        # Initialize GnuPG
        self.gpg = gnupg.GPG(gnupghome=str(self.gpg_home), verbose=False)

        # Key identity mappings
        self.trusted_identities = {
            "admin-kaisonai@pm.me": "Kai Admin",
            "user-kaisonai@pm.me": "Kai User",
            "infra-kaisonai@pm.me": "Kai Infrastructure",
            "machine-kaisonai@pm.me": "Kai Machine"
        }

        # Signature and verification logs
        self.signature_log: List[SignatureRecord] = []
        self.verification_log: List[VerificationRecord] = []

    # ==================== Key Management ====================

    async def initialize_keys(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Scan and import all PGP keys from the Kai PGP-Keys directory

        Returns:
            (success, message, import_results)
        """
        print(f"\n[*] Scanning {self.key_source_dir} for Kaisonai identities...")

        if not self.key_source_dir.exists():
            error_msg = f"Key source directory not found: {self.key_source_dir}"
            print(f"[X] {error_msg}")
            return (False, error_msg, {})

        import_results = {
            "total_files": 0,
            "total_keys_imported": 0,
            "identities": {},
            "errors": []
        }

        try:
            # Scan for .asc files
            asc_files = list(self.key_source_dir.glob("*.asc"))
            import_results["total_files"] = len(asc_files)

            if not asc_files:
                error_msg = f"No .asc files found in {self.key_source_dir}"
                print(f"[!] {error_msg}")
                return (False, error_msg, import_results)

            for key_file in asc_files:
                try:
                    key_data = key_file.read_text()
                    import_result = self.gpg.import_keys(key_data)

                    if import_result.count > 0:
                        print(f"[+] Imported {key_file.name}: {import_result.count} key(s)")
                        import_results["total_keys_imported"] += import_result.count

                        # Track imported identities
                        for uid in import_result.results:
                            if isinstance(uid, dict) and "uid" in uid:
                                identity = uid["uid"]
                                if identity not in import_results["identities"]:
                                    import_results["identities"][identity] = {
                                        "fingerprint": uid.get("fingerprint"),
                                        "status": "imported"
                                    }
                    else:
                        warn_msg = f"No keys found in {key_file.name}"
                        print(f"[!] {warn_msg}")
                        import_results["errors"].append(warn_msg)

                except Exception as e:
                    error_msg = f"Failed to import {key_file.name}: {str(e)}"
                    print(f"[X] {error_msg}")
                    import_results["errors"].append(error_msg)

            # Verify trusted identities are loaded
            print("\n[*] Verifying trusted identities...")
            missing_identities = []
            for identity in self.trusted_identities.keys():
                keys = self.gpg.list_keys(keys=identity)
                if keys:
                    print(f"[OK] Trusted identity loaded: {identity}")
                else:
                    missing_identities.append(identity)
                    print(f"[!] Warning: {identity} not found in imported keys")

            if missing_identities:
                warn_msg = f"Missing identities: {', '.join(missing_identities)}"
                print(f"[!] {warn_msg}")
                import_results["errors"].append(warn_msg)

            message = f"Initialized crypto system: {import_results['total_keys_imported']} keys imported"
            print(f"\n[OK] {message}")

            return (True, message, import_results)

        except Exception as e:
            error_msg = f"Key initialization failed: {str(e)}"
            print(f"[X] {error_msg}")
            return (False, error_msg, import_results)

    def list_available_keys(self) -> List[Dict[str, Any]]:
        """List all available keys in the GPG home directory"""
        keys = self.gpg.list_keys()
        result = []

        for key in keys:
            result.append({
                "fingerprint": key["fingerprint"],
                "keyid": key["keyid"],
                "uids": key["uids"],
                "type": key["type"],
                "length": key.get("length", "unknown"),
                "expires": key.get("expires", "never"),
                "validity": key.get("validity", "unknown")
            })

        return result

    # ==================== Artifact Signing ====================

    async def sign_artifact(
        self,
        artifact_path: str,
        passphrase: str = "",
        output_path: Optional[str] = None
    ) -> Tuple[bool, str, Optional[SignatureRecord]]:
        """
        Sign an artifact (vulnerability report, scan log, etc.) with machine identity

        Creates a detached signature file that can be verified independently

        Args:
            artifact_path: Path to the file to sign
            passphrase: Passphrase for the machine private key
            output_path: Custom path for signature file (default: artifact.sig)

        Returns:
            (success, message, signature_record)
        """
        artifact_file = Path(artifact_path)

        if not artifact_file.exists():
            error_msg = f"Artifact not found: {artifact_path}"
            print(f"[X] {error_msg}")
            return (False, error_msg, None)

        print(f"\n[*] Signing artifact with identity: {self.machine_identity}")
        print(f"    Artifact: {artifact_file.name}")

        sig_path = output_path or f"{artifact_path}.sig"

        try:
            # Calculate artifact hash for chain of custody
            artifact_hash = self._calculate_hash(artifact_path)
            print(f"    SHA256: {artifact_hash}")

            # Read artifact
            with open(artifact_path, 'rb') as f:
                artifact_data = f.read()

            # Sign with machine identity (detached signature)
            sign_result = self.gpg.sign_file(
                f.__enter__() if hasattr(f, '__enter__') else artifact_data,
                keyid=self.machine_identity,
                passphrase=passphrase,
                detach=True,
                output=sig_path
            )

            # Close file properly
            if artifact_path:
                with open(artifact_path, 'rb') as f:
                    sign_result = self.gpg.sign_file(
                        f,
                        keyid=self.machine_identity,
                        passphrase=passphrase,
                        detach=True,
                        output=sig_path
                    )

            if sign_result.status == "signature created":
                print(f"[!] Artifact signed successfully: {sig_path}")

                # Get key fingerprint for record
                keys = self.gpg.list_keys(keys=self.machine_identity)
                fingerprint = keys[0]["fingerprint"] if keys else "unknown"

                # Create signature record
                record = SignatureRecord(
                    artifact_path=str(artifact_path),
                    signature_path=sig_path,
                    signer_identity=self.machine_identity,
                    signer_fingerprint=fingerprint,
                    signed_at=datetime.utcnow(),
                    algorithm="RSA",
                    artifact_hash=artifact_hash,
                    signature_valid=True
                )

                self.signature_log.append(record)
                self._log_audit("sign_artifact", {
                    "artifact": artifact_file.name,
                    "identity": self.machine_identity,
                    "hash": artifact_hash
                })

                return (True, f"Artifact signed: {sig_path}", record)
            else:
                error_msg = f"Signing failed: {sign_result.stderr}"
                print(f"[X] {error_msg}")
                return (False, error_msg, None)

        except Exception as e:
            error_msg = f"Signing operation failed: {str(e)}"
            print(f"[X] {error_msg}")
            return (False, error_msg, None)

    # ==================== Artifact Verification ====================

    async def verify_artifact(
        self,
        artifact_path: str,
        signature_path: str
    ) -> Tuple[bool, str, Optional[VerificationRecord]]:
        """
        Verify that an artifact was signed by a trusted Kaisonai identity

        Detects tampering and verifies chain of custody

        Args:
            artifact_path: Path to the artifact file
            signature_path: Path to the signature file

        Returns:
            (success, message, verification_record)
        """
        artifact_file = Path(artifact_path)
        sig_file = Path(signature_path)

        if not artifact_file.exists():
            error_msg = f"Artifact not found: {artifact_path}"
            print(f"[X] {error_msg}")
            return (False, error_msg, None)

        if not sig_file.exists():
            error_msg = f"Signature not found: {signature_path}"
            print(f"[X] {error_msg}")
            return (False, error_msg, None)

        print(f"\n[*] Verifying signature for: {artifact_file.name}")

        try:
            # Calculate current artifact hash
            current_hash = self._calculate_hash(artifact_path)
            print(f"    Current SHA256: {current_hash}")

            # Verify signature
            with open(sig_file, 'rb') as f:
                verify_result = self.gpg.verify_file(f, artifact_path)

            # Parse verification results
            status = VerificationStatus.UNSIGNED
            tampered = False
            signer_identity = "unknown"
            signer_fingerprint = "unknown"
            details = {
                "status_return": verify_result.status,
                "signature_id": verify_result.signature_id,
                "key_id": verify_result.key_id,
                "username": verify_result.username
            }

            if verify_result.status == "signature valid":
                status = VerificationStatus.VALID
                signer_identity = verify_result.username or "unknown"
                signer_fingerprint = verify_result.fingerprint

                # Check if signer is in trusted identities
                is_trusted = any(
                    trusted_id in signer_identity
                    for trusted_id in self.trusted_identities.keys()
                )

                if is_trusted:
                    print(f"[OK] VERIFIED: Signed by {signer_identity}")
                    print(f"     Fingerprint: {signer_fingerprint}")
                else:
                    status = VerificationStatus.UNTRUSTED
                    print(f"[!] WARNING: Signed by untrusted identity: {signer_identity}")

            elif verify_result.status == "signature invalid":
                status = VerificationStatus.TAMPERED
                tampered = True
                print(f"[X] TAMPER DETECTED! Signature is invalid")
                print(f"[X] This indicates the artifact has been modified")

            else:
                print(f"[!] Verification inconclusive: {verify_result.status}")

            # Create verification record
            record = VerificationRecord(
                artifact_path=str(artifact_path),
                signature_path=str(signature_path),
                verified_at=datetime.utcnow(),
                status=status,
                signer_identity=signer_identity,
                signer_fingerprint=signer_fingerprint,
                tamper_detected=tampered,
                details=details
            )

            self.verification_log.append(record)
            self._log_audit("verify_artifact", {
                "artifact": artifact_file.name,
                "status": status.value,
                "tamper_detected": tampered,
                "signer": signer_identity
            })

            if tampered:
                return (False, "TAMPER ALERT: Artifact signature verification failed", record)
            elif status == VerificationStatus.VALID:
                return (True, f"Signature verified: {signer_identity}", record)
            else:
                return (False, f"Signature verification inconclusive: {status.value}", record)

        except Exception as e:
            error_msg = f"Verification operation failed: {str(e)}"
            print(f"[X] {error_msg}")
            return (False, error_msg, None)

    # ==================== Chain of Custody ====================

    def get_chain_of_custody(self, artifact_path: str) -> Dict[str, Any]:
        """
        Get complete chain of custody for an artifact

        Returns all signing and verification operations associated with the artifact
        """
        signatures = [
            {
                "signed_at": s.signed_at.isoformat(),
                "signer": s.signer_identity,
                "fingerprint": s.signer_fingerprint,
                "artifact_hash": s.artifact_hash
            }
            for s in self.signature_log
            if s.artifact_path == artifact_path
        ]

        verifications = [
            {
                "verified_at": v.verified_at.isoformat(),
                "status": v.status.value,
                "signer": v.signer_identity,
                "tamper_detected": v.tamper_detected
            }
            for v in self.verification_log
            if v.artifact_path == artifact_path
        ]

        return {
            "artifact": artifact_path,
            "signatures": signatures,
            "verifications": verifications,
            "chain_intact": len(verifications) > 0 and not any(v["tamper_detected"] for v in verifications)
        }

    # ==================== Audit Logging ====================

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get complete audit trail of crypto operations"""
        return self._audit_log

    def _log_audit(self, operation: str, details: Dict[str, Any]):
        """Log an audit event"""
        if not hasattr(self, "_audit_log"):
            self._audit_log = []

        self._audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "details": details
        })

    # ==================== Helper Methods ====================

    def _calculate_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # ==================== Status & Diagnostics ====================

    def get_system_status(self) -> Dict[str, Any]:
        """Get current crypto system status"""
        return {
            "gpg_home": str(self.gpg_home),
            "gpg_home_permissions": oct(os.stat(self.gpg_home).st_mode)[-3:],
            "machine_identity": self.machine_identity,
            "available_keys": len(self.list_available_keys()),
            "signature_operations": len(self.signature_log),
            "verification_operations": len(self.verification_log),
            "trusted_identities": list(self.trusted_identities.keys())
        }


# Global crypto system instance
kai_crypto_system = None


def initialize_kai_crypto(
    gpg_home: str = None,
    key_source_dir: str = None
) -> KaiCryptoSystem:
    """Initialize the global Kai crypto system"""
    global kai_crypto_system

    kai_crypto_system = KaiCryptoSystem(
        gpg_home=gpg_home,
        key_source_dir=key_source_dir
    )

    return kai_crypto_system


def get_kai_crypto() -> KaiCryptoSystem:
    """Get the global Kai crypto system"""
    global kai_crypto_system

    if kai_crypto_system is None:
        kai_crypto_system = KaiCryptoSystem()

    return kai_crypto_system
