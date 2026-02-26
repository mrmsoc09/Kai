# Kai Building Agent Prompt & Implementation Guide

## Executive Mission Brief

**Agent Role**: Lead Systems Engineer for Project Kai

**Objective**: Develop and deploy a robust Python-based **Security Module** that handles **automated logging, artifact signing, and report verification** using the established PGP cryptographic infrastructure.

**Authority Level**: Full system access to `/home/user/kai/Kai PGP-Keys` directory and Kai infrastructure

---

## Mission Strategy & Architecture

You are to implement a comprehensive cryptographic chain of custody system that:

1. **Auto-discovers and imports all Kaisonai PGP keys** from a centralized repository
2. **Manages the machine signing identity** (`machine-kaisonai@pm.me`) for automated operations
3. **Automatically signs all vulnerability reports and scan logs** with tamper-proof detached signatures
4. **Verifies the origin and integrity** of all critical artifacts
5. **Triggers tamper alerts** if any signatures fail verification
6. **Maintains an immutable audit trail** of all cryptographic operations

---

## Architectural Requirements

### 1. Key Discovery & Import Module

**Location**: `/home/user/kai/Kai PGP-Keys`

**Objective**: Scan the key directory and import public keys for all trusted Kaisonai identities.

**Implementation**:
```python
from pathlib import Path
import gnupg

KEY_SOURCE_DIR = Path("/home/user/kai/Kai PGP-Keys")
GPG_HOME = Path.home() / ".kai" / "gpg_home"

# Create secure GPG home (700 permissions)
GPG_HOME.mkdir(mode=0o700, parents=True, exist_ok=True)

# Initialize GnuPG
gpg = gnupg.GPG(gnupghome=str(GPG_HOME))

# Scan for .asc files
for key_file in KEY_SOURCE_DIR.glob("*.asc"):
    key_data = key_file.read_text()
    import_result = gpg.import_keys(key_data)
    print(f"[+] Imported {key_file.name}: {import_result.count} keys")
```

**Expected Identities to Load**:
- `admin-kaisonai@pm.me` (Admin PGP public key)
- `user-kaisonai@pm.me` (User PGP public key)
- `infra-kaisonai@pm.me` (Infrastructure PGP public key)
- `machine-kaisonai@pm.me` (Machine private key - CRITICAL)

**Output**: Confirmation of all four identities loaded into `~/.kai/gpg_home`

---

### 2. Secret Management (Machine Identity)

**Critical Security Requirement**: Only the `machine-kaisonai@pm.me` private key should be imported and stored.

**Implementation**:
```python
def import_machine_key(gpg, machine_identity="machine-kaisonai@pm.me"):
    """Import the machine signing identity (private key)"""
    key_file = KEY_SOURCE_DIR / "machine-kaisonai@pm.me.asc"

    if not key_file.exists():
        raise FileNotFoundError(f"Machine key not found: {key_file}")

    key_data = key_file.read_text()
    import_result = gpg.import_keys(key_data)

    if import_result.count == 0:
        raise ValueError("Failed to import machine key")

    print(f"[OK] Machine identity imported: {machine_identity}")
    return import_result
```

**Trust Model**:
- Machine key stored encrypted at rest (`~/.kai/gpg_home` with 700 permissions)
- Only the Kai process has access to this directory
- All signing operations use this identity
- All signatures contain the machine fingerprint for audit trail

---

### 3. Automated Artifact Signing Module

**Function**: `sign_hunt_artifact(file_path, passphrase="")`

**Purpose**: Generate detached PGP signatures (`.sig` files) for vulnerability reports and scan logs

**Implementation**:
```python
def sign_hunt_artifact(file_path, passphrase="", machine_identity="machine-kaisonai@pm.me"):
    """
    Sign a vulnerability report or scan log with machine identity
    Creates a detached signature file (artifact.sig)
    """
    artifact = Path(file_path)

    if not artifact.exists():
        raise FileNotFoundError(f"Artifact not found: {file_path}")

    sig_path = f"{file_path}.sig"

    # Read artifact
    with open(artifact, 'rb') as f:
        # Generate detached signature
        status = gpg.sign_file(
            f,
            keyid=machine_identity,
            passphrase=passphrase,
            detach=True,
            output=sig_path
        )

    if status.status == "signature created":
        print(f"[!] Artifact signed: {sig_path}")
        print(f"    Signer: {machine_identity}")
        return sig_path
    else:
        raise ValueError(f"Signing failed: {status.stderr}")
```

**Usage Example**:
```python
# Sign a vulnerability report
report_path = "/var/lib/kai/reports/CVE-2025-12345_report.json"
sig_path = sign_hunt_artifact(report_path, passphrase="machine_passphrase")

# Signature file now exists at:
# /var/lib/kai/reports/CVE-2025-12345_report.json.sig
```

**Output Format**:
```
-----BEGIN PGP SIGNATURE-----

iQIzBAEBCAAdFiEE8F7tVKtPrz5QxYfFg7dq8mNjAVwFAmXfxK0ACgkQg7dq8mNj
...signature content...
-----END PGP SIGNATURE-----
```

---

### 4. Reputation Verification Module

**Function**: `verify_origin(artifact_path, signature_path)`

**Purpose**: Cross-reference signatures against imported public keys to detect tampering

**Implementation**:
```python
def verify_origin(artifact_path, signature_path):
    """
    Verify that an artifact was signed by a trusted Kaisonai identity
    Returns:
        - True if signature valid and from trusted identity
        - Raises exception if tampering detected
    """
    artifact = Path(artifact_path)
    sig_file = Path(signature_path)

    if not artifact.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_path}")

    if not sig_file.exists():
        raise FileNotFoundError(f"Signature not found: {signature_path}")

    # Verify signature
    with open(sig_file, 'rb') as f:
        verified = gpg.verify_file(f, str(artifact))

    if verified.status == "signature valid":
        print(f"[OK] VERIFIED: Signed by {verified.username}")
        print(f"     Fingerprint: {verified.fingerprint}")

        # Check if signer is trusted
        trusted_ids = [
            "admin-kaisonai@pm.me",
            "user-kaisonai@pm.me",
            "infra-kaisonai@pm.me",
            "machine-kaisonai@pm.me"
        ]

        is_trusted = any(tid in verified.username for tid in trusted_ids)

        if is_trusted:
            return True
        else:
            raise ValueError(f"Signature from untrusted identity: {verified.username}")

    elif verified.status == "signature invalid":
        # TAMPER DETECTED
        print("[X] TAMPER ALERT: Signature verification failed")
        print("[X] Artifact has been modified or compromised")
        raise ValueError("TAMPER DETECTION: Artifact signature verification failed")

    else:
        raise ValueError(f"Verification inconclusive: {verified.status}")
```

**Tamper Alert Procedure**:
```python
try:
    verify_origin(report_path, sig_path)
except ValueError as e:
    if "TAMPER DETECTION" in str(e):
        # HALT EXECUTION PIPELINE
        print("[X] TAMPER ALERT TRIGGERED")
        print("[X] Halting all operations")
        print("[X] Escalating to security team")

        # Log incident
        log_tamper_incident(report_path, sig_path)

        # Stop processing
        sys.exit(1)
```

---

### 5. Descriptive Logging Module

**Requirement**: Every cryptographic operation must output verbose, descriptive logging to STDOUT

**Implementation**:
```python
def print_operation_header(operation, identity):
    """Print descriptive header for crypto operation"""
    print(f"\n[*] {operation}")
    print(f"    Identity: {identity}")
    print(f"    Timestamp: {datetime.utcnow().isoformat()}")

def print_signature_result(artifact_path, sig_path, machine_identity):
    """Print signature operation result"""
    print(f"[!] Artifact signed successfully")
    print(f"    Artifact: {artifact_path}")
    print(f"    Signature: {sig_path}")
    print(f"    Signer: {machine_identity}")

    # Calculate and display hash
    artifact_hash = sha256(Path(artifact_path).read_bytes()).hexdigest()
    print(f"    SHA256: {artifact_hash}")

def print_verification_result(status, signer, fingerprint):
    """Print verification operation result"""
    if status == "valid":
        print(f"[OK] Signature verified")
        print(f"     Signer: {signer}")
        print(f"     Fingerprint: {fingerprint}")
    elif status == "invalid":
        print(f"[X] TAMPER DETECTED")
        print(f"[X] Signature verification failed")
```

**Example Output**:
```
[*] Signing artifact
    Identity: machine-kaisonai@pm.me
    Timestamp: 2026-02-02T12:00:00

[!] Artifact signed successfully
    Artifact: /var/lib/kai/reports/CVE-2025-12345_report.json
    Signature: /var/lib/kai/reports/CVE-2025-12345_report.json.sig
    Signer: machine-kaisonai@pm.me
    SHA256: abc123def456...

[*] Verifying artifact
    Identity: machine-kaisonai@pm.me
    Timestamp: 2026-02-02T12:01:00

[OK] Signature verified
     Signer: Machine Kaisonai <machine-kaisonai@pm.me>
     Fingerprint: 8F7E6D5C4B3A2F1E
```

---

## Implementation Constraints

### Security Requirements

1. **GnuPG Home Directory Permissions**
   ```bash
   chmod 700 ~/.kai/gpg_home
   ```

2. **Private Key Storage**
   - Only `machine-kaisonai@pm.me` private key stored locally
   - All other keys are public keys only
   - Passphrase-protected (can be passed as environment variable)

3. **Signature Verification**
   - All signatures verified against imported public keys
   - Fingerprint validation required
   - Untrusted signer rejection

4. **Tamper Detection Protocol**
   ```python
   if signature_verification_fails:
       trigger_tamper_alert()
       halt_execution_pipeline()
       escalate_to_security_team()
       log_incident_with_full_context()
   ```

### Library Requirements

**Primary**: `python-gnupg`

```bash
pip install python-gnupg
```

**Alternative**: `gpg-json` or direct `gpg` CLI with subprocess (less recommended)

### Environment Variables

```bash
# GPG home directory
export KAI_GPG_HOME=$HOME/.kai/gpg_home

# Key source directory
export KAI_KEY_DIR=/home/user/kai/Kai PGP-Keys

# Machine passphrase (for unattended signing)
export KAI_MACHINE_PASSPHRASE=<secure_passphrase>

# Machine identity
export KAI_MACHINE_IDENTITY=machine-kaisonai@pm.me
```

---

## Integration Points with Kai v7.5

### 1. Artifact Signing Workflow

When a hunting session completes:
```python
# 1. Validate findings through HiL approval
approved_findings = await hil_workflow.request_approval(...)

# 2. Generate vulnerability report
report = await reporter_agent.generate_report(approved_findings)

# 3. SIGN the report with machine identity
sig_path = kai_crypto.sign_artifact(report_path, passphrase)

# 4. Record in orchestration graph
await orchestration_graph.add_event("report_signed", {
    "report": report_path,
    "signature": sig_path,
    "signer": "machine-kaisonai@pm.me"
})

# 5. Submit signed report to bounty platform
await reporter_agent.submit_with_signature(report, sig_path)
```

### 2. Cross-Verification on Bounty Platform

Bounty platforms (HackerOne, Bugcrowd) can verify:
```python
# Platform receives report + signature
# Imports machine-kaisonai@pm.me public key from Kai PGP-Keys
# Verifies signature
# If valid: Confirms authenticity and chain of custody
# If invalid: Flags as tampered/fraudulent
```

### 3. Agent Skill Validation

When agents complete critical tasks:
```python
# Agent completes exploitation phase
exploit_poc = weaponizer_agent.generate_payload()

# Sign the PoC
sig = kai_crypto.sign_artifact(exploit_poc)

# Auditor verifies before approval
verified = kai_crypto.verify_artifact(exploit_poc, sig)

# If tamper detected: escalate to admin review
if not verified:
    await hil_workflow.escalate_approval(
        approval_id,
        escalation_reason="Artifact tampering detected"
    )
```

### 4. Episodic Memory Signing

When agents record learned patterns:
```python
# Memory manager records technique success rate
memory = {
    "technique": "sql_injection_union_based",
    "success_rate": 0.87,
    "target_type": "web_application"
}

# Sign memory entry
memory_json = json.dumps(memory)
sig_path = kai_crypto.sign_artifact(memory_json)

# Store in episodic memory with signature
episodic_memory.store(memory, signature=sig_path)
```

---

## Complete Implementation Example

### File: `kai_crypto.py`

```python
#!/usr/bin/env python3
"""
Kai Cryptographic Artifact Signing System
Handles automated PGP signing and verification for vulnerability reports
"""

import gnupg
import os
import sys
from pathlib import Path
from datetime import datetime
import hashlib
import json

class KaiCryptoAgent:
    def __init__(self):
        self.gpg_home = Path.home() / ".kai" / "gpg_home"
        self.key_source = Path("/home/user/kai/Kai PGP-Keys")
        self.machine_identity = "machine-kaisonai@pm.me"

        # Create secure GPG home
        self.gpg_home.mkdir(mode=0o700, parents=True, exist_ok=True)

        # Initialize GnuPG
        self.gpg = gnupg.GPG(gnupghome=str(self.gpg_home))

    def initialize_kaisonai_keys(self):
        """Import all Kaisonai identities"""
        print(f"[*] Scanning {self.key_source} for Kaisonai identities...")

        for key_file in self.key_source.glob("*.asc"):
            key_data = key_file.read_text()
            result = self.gpg.import_keys(key_data)
            print(f"[+] Imported {key_file.name}: {result.count} keys")

    def sign_artifact(self, file_path, passphrase=""):
        """Sign an artifact with machine identity"""
        print(f"\n[*] Signing artifact")
        print(f"    Identity: {self.machine_identity}")
        print(f"    File: {file_path}")

        artifact = Path(file_path)
        sig_path = f"{file_path}.sig"

        with open(artifact, 'rb') as f:
            status = self.gpg.sign_file(
                f,
                keyid=self.machine_identity,
                passphrase=passphrase,
                detach=True,
                output=sig_path
            )

        if status.status == "signature created":
            print(f"[!] Signed: {sig_path}")
            return sig_path
        else:
            print(f"[X] Signing failed: {status.stderr}")
            raise ValueError("Signing failed")

    def verify_artifact(self, file_path, sig_path):
        """Verify artifact signature"""
        print(f"\n[*] Verifying artifact")
        print(f"    File: {file_path}")

        with open(sig_path, 'rb') as f:
            verified = self.gpg.verify_file(f, file_path)

        if verified.status == "signature valid":
            print(f"[OK] VERIFIED: {verified.username}")
            print(f"     Fingerprint: {verified.fingerprint}")
            return True
        elif verified.status == "signature invalid":
            print(f"[X] TAMPER ALERT: Signature verification failed")
            print(f"[X] Halting execution pipeline")
            sys.exit(1)
        else:
            print(f"[!] Inconclusive: {verified.status}")
            return False

if __name__ == "__main__":
    agent = KaiCryptoAgent()
    agent.initialize_kaisonai_keys()

    # Example usage
    # sig = agent.sign_artifact("report.json", passphrase="...")
    # agent.verify_artifact("report.json", "report.json.sig")
```

---

## Testing & Validation

### Test Case 1: Key Import

```bash
python3 -c "
from kai_crypto import KaiCryptoAgent
agent = KaiCryptoAgent()
agent.initialize_kaisonai_keys()
print('SUCCESS: All keys imported')
"
```

### Test Case 2: Artifact Signing

```bash
echo '{"vulnerability": "CVE-2025-12345"}' > test_report.json
python3 -c "
from kai_crypto import KaiCryptoAgent
agent = KaiCryptoAgent()
agent.sign_artifact('test_report.json', passphrase='test')
print('SUCCESS: Report signed')
"
```

### Test Case 3: Signature Verification

```bash
python3 -c "
from kai_crypto import KaiCryptoAgent
agent = KaiCryptoAgent()
agent.verify_artifact('test_report.json', 'test_report.json.sig')
print('SUCCESS: Signature valid')
"
```

### Test Case 4: Tamper Detection

```bash
# Modify the report
echo '{"vulnerability": "TAMPERED"}' > test_report.json

# Try to verify - should fail
python3 -c "
from kai_crypto import KaiCryptoAgent
agent = KaiCryptoAgent()
agent.verify_artifact('test_report.json', 'test_report.json.sig')
"
# Expected: [X] TAMPER ALERT and exit(1)
```

---

## Deployment Checklist

- [ ] `python-gnupg` installed on target system
- [ ] `/home/user/kai/Kai PGP-Keys` directory exists and contains all `.asc` files
- [ ] `~/.kai/gpg_home` created with `700` permissions
- [ ] All four identities successfully imported
- [ ] Machine identity private key accessible
- [ ] Passphrase management configured (environment variable or secure vault)
- [ ] Audit logging enabled
- [ ] Integration with Kai v7.5 complete
- [ ] Bounty platforms can verify machine signature
- [ ] Tamper alert escalation configured

---

## Security Operations

### Daily Checklist

1. **Verify key integrity**: `gpg --list-keys`
2. **Check tamper log**: Review all failed verifications
3. **Monitor signing operations**: Ensure machine identity is used exclusively
4. **Validate signatures**: Spot-check recent artifacts

### Incident Response

If tamper detected:
1. **STOP** - Halt execution immediately
2. **LOG** - Record artifact path, signature, and timestamp
3. **ESCALATE** - Notify security team
4. **INVESTIGATE** - Determine tampering source
5. **RECOVER** - Restore from clean backup

---

## Next Steps

**Phase 1**: Implement and test `kai_crypto.py`

**Phase 2**: Integrate with Kai v7.5 artifact signing endpoints

**Phase 3**: Deploy to production with audit logging

**Phase 4** (Future): Agent-Zero approval plugin requiring user PGP signature before executing exploits

---

For detailed API reference, see `API_ARTIFACT_SIGNING.md`.
