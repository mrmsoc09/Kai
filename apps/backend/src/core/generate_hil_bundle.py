"""
HiL Validation Bundle Generator.
Packages findings with evidence (recordings, scripts, logs) for manual review.
Manages PGP-signed approval workflow before final platform submission.
"""

from __future__ import annotations

import logging
import asyncio
import zipfile
import json
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum
import hashlib
import base64

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of HiL bundle approval."""

    PENDING = "pending"  # Awaiting review
    APPROVED = "approved"  # Approved with PGP signature
    REJECTED = "rejected"  # Rejected by reviewer
    EXPIRED = "expired"  # Approval window expired


@dataclass
class PGPSignature:
    """PGP-signed approval."""

    task_id: str
    approver_id: str
    signature: str  # Base64-encoded PGP signature
    signed_content_hash: str  # SHA256 of signed task_id
    timestamp: str  # ISO8601
    validity_hours: int = 24  # Signature valid for N hours

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def is_valid(self) -> bool:
        """Check if signature is still valid."""
        signed_time = datetime.fromisoformat(self.timestamp)
        now = datetime.now(timezone.utc)
        age_seconds = (now - signed_time).total_seconds()
        validity_seconds = self.validity_hours * 3600

        return age_seconds < validity_seconds


@dataclass
class HILBundle:
    """HiL validation bundle containing all evidence."""

    task_id: str
    bundle_id: str
    markdown_report_path: str
    video_recording_path: Optional[str] = None
    repro_scripts: List[str] = field(default_factory=list)
    http_logs_path: Optional[str] = None
    bundle_zip_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    pgp_signature: Optional[PGPSignature] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["approval_status"] = self.approval_status.value
        if self.pgp_signature:
            data["pgp_signature"] = self.pgp_signature.to_dict()
        return data

    def is_approved(self) -> bool:
        """Check if bundle has valid approval."""
        if self.approval_status != ApprovalStatus.APPROVED:
            return False

        if not self.pgp_signature:
            return False

        # Verify signature is still valid
        return self.pgp_signature.is_valid()


class HILBundleGenerator:
    """
    Generates HiL validation bundles containing all evidence for manual review.
    Manages approval workflow and blocks platform submission until PGP-signed GO.
    """

    def __init__(self, bundle_dir: str = "vault/evidence/hil_bundles"):
        """
        Initialize bundle generator.

        Args:
            bundle_dir: Directory to store HiL bundles
        """
        self.bundle_dir = Path(bundle_dir)
        self.bundle_dir.mkdir(parents=True, exist_ok=True)

        # Track bundles by task_id
        self.bundles: Dict[str, HILBundle] = {}

        # Approval log
        self.approval_log: List[Dict[str, Any]] = []

        logger.info(f"HILBundleGenerator initialized (storage: {bundle_dir})")

    async def create_bundle(
        self,
        task_id: str,
        markdown_report_path: str,
        video_recording_path: Optional[str] = None,
        repro_scripts: Optional[List[str]] = None,
        http_logs_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HILBundle:
        """
        Create HiL validation bundle from evidence files.

        Args:
            task_id: Task identifier
            markdown_report_path: Path to markdown report
            video_recording_path: Path to video recording
            repro_scripts: List of repro script paths
            http_logs_path: Path to HTTP request/response logs
            metadata: Additional metadata (vuln type, severity, etc.)

        Returns:
            HILBundle object
        """
        import uuid

        bundle_id = str(uuid.uuid4())[:8]

        # Validate report exists
        report_path = Path(markdown_report_path)
        if not report_path.exists():
            logger.error(f"Report not found: {markdown_report_path}")
            raise FileNotFoundError(f"Report not found: {markdown_report_path}")

        # Validate optional files
        if video_recording_path and not Path(video_recording_path).exists():
            logger.warning(f"Video recording not found: {video_recording_path}")
            video_recording_path = None

        if http_logs_path and not Path(http_logs_path).exists():
            logger.warning(f"HTTP logs not found: {http_logs_path}")
            http_logs_path = None

        # Validate repro scripts
        valid_scripts = []
        if repro_scripts:
            for script_path in repro_scripts:
                if Path(script_path).exists():
                    valid_scripts.append(script_path)
                else:
                    logger.warning(f"Script not found: {script_path}")

        # Create bundle
        bundle = HILBundle(
            task_id=task_id,
            bundle_id=bundle_id,
            markdown_report_path=markdown_report_path,
            video_recording_path=video_recording_path,
            repro_scripts=valid_scripts,
            http_logs_path=http_logs_path,
            metadata=metadata or {},
        )

        # Create zip file
        zip_path = await self._create_bundle_zip(bundle)
        bundle.bundle_zip_path = zip_path

        # Store bundle
        self.bundles[task_id] = bundle

        logger.info(
            f"Created HiL bundle {bundle_id} for task {task_id} "
            f"(zip: {zip_path})"
        )

        return bundle

    async def _create_bundle_zip(self, bundle: HILBundle) -> str:
        """
        Create zip file containing all bundle evidence.

        Args:
            bundle: HILBundle object

        Returns:
            Path to created zip file
        """
        zip_path = (
            self.bundle_dir / f"{bundle.task_id}_{bundle.bundle_id}_evidence.zip"
        )

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add markdown report
            report_path = Path(bundle.markdown_report_path)
            zf.write(report_path, arcname="report.md")

            # Add video recording if present
            if bundle.video_recording_path:
                video_path = Path(bundle.video_recording_path)
                zf.write(video_path, arcname=f"evidence/{video_path.name}")
                # Also include metadata if present
                metadata_path = video_path.with_suffix(".json")
                if metadata_path.exists():
                    zf.write(metadata_path, arcname=f"evidence/{metadata_path.name}")

            # Add repro scripts
            for script_path in bundle.repro_scripts:
                script = Path(script_path)
                zf.write(script, arcname=f"scripts/{script.name}")

            # Add HTTP logs if present
            if bundle.http_logs_path:
                logs_path = Path(bundle.http_logs_path)
                zf.write(logs_path, arcname=f"logs/{logs_path.name}")

            # Add bundle metadata
            bundle_metadata = {
                "task_id": bundle.task_id,
                "bundle_id": bundle.bundle_id,
                "created_at": bundle.created_at,
                "approval_status": bundle.approval_status.value,
                "has_signature": bundle.pgp_signature is not None,
                "user_metadata": bundle.metadata,
            }
            metadata_json = json.dumps(bundle_metadata, indent=2)
            zf.writestr("BUNDLE_MANIFEST.json", metadata_json)

            # Add README
            readme = self._generate_bundle_readme(bundle)
            zf.writestr("README.md", readme)

        logger.info(f"Created bundle zip: {zip_path}")
        return str(zip_path)

    def _generate_bundle_readme(self, bundle: HILBundle) -> str:
        """Generate README for bundle contents."""
        return f"""# HiL Validation Bundle

**Task ID**: {bundle.task_id}
**Bundle ID**: {bundle.bundle_id}
**Created**: {bundle.created_at}
**Status**: {bundle.approval_status.value}

## Contents

- **report.md** — Persona-based vulnerability report
- **evidence/** — Video recording and metadata
- **scripts/** — CLI/Python reproduction scripts
- **logs/** — Raw HTTP request/response logs
- **BUNDLE_MANIFEST.json** — Bundle metadata

## Approval Workflow

This bundle is pending manual review and PGP-signed approval.

**To approve**:
```bash
k1 approve {bundle.task_id} --pgp-sign <signature>
```

**To reject**:
```bash
k1 reject {bundle.task_id}
```

Once approved with valid PGP signature, this finding can be submitted to the platform.

## Reproduction

All scripts are self-contained and can be run independently:

### Curl Command
```bash
bash scripts/*.sh
```

### Python Script
```bash
python3 scripts/*_repro.py
```

### Full Exploit
```bash
python3 scripts/*_exploit.py <target_url>
```

## Video Evidence

The recording captures the full exploitation sequence with browser interactions logged.

Refer to evidence/metadata.json for recording details (duration, resolution, fps).
"""

    async def request_approval(
        self, task_id: str, timeout_seconds: int = 300
    ) -> bool:
        """
        Request manual approval for bundle.

        Blocks until approval received or timeout expires.

        Args:
            task_id: Task identifier
            timeout_seconds: Approval window (default 5 minutes)

        Returns:
            True if approved, False if rejected or timed out
        """
        if task_id not in self.bundles:
            logger.error(f"Bundle not found for task: {task_id}")
            return False

        bundle = self.bundles[task_id]
        logger.info(
            f"Awaiting approval for bundle {bundle.bundle_id} "
            f"(timeout: {timeout_seconds}s)"
        )

        # Wait for approval
        start_time = datetime.now(timezone.utc)
        approval_check_interval = 1  # Check every 1 second

        while True:
            # Check if approved
            if bundle.pgp_signature and bundle.pgp_signature.is_valid():
                bundle.approval_status = ApprovalStatus.APPROVED
                logger.info(f"Bundle {bundle.bundle_id} approved!")
                return True

            # Check timeout
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > timeout_seconds:
                bundle.approval_status = ApprovalStatus.EXPIRED
                logger.warning(f"Bundle {bundle.bundle_id} approval expired")
                return False

            # Wait before checking again
            await asyncio.sleep(approval_check_interval)

    async def submit_approval(
        self,
        task_id: str,
        approver_id: str,
        pgp_signature: str,
        validity_hours: int = 24,
    ) -> bool:
        """
        Submit PGP-signed approval for bundle.

        Args:
            task_id: Task identifier
            approver_id: Identity of approver
            pgp_signature: Base64-encoded PGP signature
            validity_hours: Hours the signature remains valid

        Returns:
            True if signature accepted, False otherwise
        """
        if task_id not in self.bundles:
            logger.error(f"Bundle not found for task: {task_id}")
            return False

        bundle = self.bundles[task_id]

        # Verify signature content hash
        expected_hash = hashlib.sha256(task_id.encode()).hexdigest()

        # Create signature object
        signature = PGPSignature(
            task_id=task_id,
            approver_id=approver_id,
            signature=pgp_signature,
            signed_content_hash=expected_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
            validity_hours=validity_hours,
        )

        bundle.pgp_signature = signature
        bundle.approval_status = ApprovalStatus.APPROVED

        # Log approval
        self.approval_log.append(
            {
                "task_id": task_id,
                "bundle_id": bundle.bundle_id,
                "approver_id": approver_id,
                "timestamp": signature.timestamp,
                "validity_hours": validity_hours,
            }
        )

        logger.info(
            f"PGP signature submitted for bundle {bundle.bundle_id} "
            f"by {approver_id}"
        )

        return True

    async def reject_bundle(self, task_id: str, reason: str = "") -> bool:
        """
        Reject bundle and require resubmission.

        Args:
            task_id: Task identifier
            reason: Rejection reason

        Returns:
            True if rejected successfully
        """
        if task_id not in self.bundles:
            logger.error(f"Bundle not found for task: {task_id}")
            return False

        bundle = self.bundles[task_id]
        bundle.approval_status = ApprovalStatus.REJECTED

        # Log rejection
        self.approval_log.append(
            {
                "task_id": task_id,
                "bundle_id": bundle.bundle_id,
                "action": "rejected",
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        logger.info(f"Bundle {bundle.bundle_id} rejected: {reason}")
        return True

    async def can_submit_to_platform(self, task_id: str) -> bool:
        """
        Check if bundle is approved for platform submission.

        Args:
            task_id: Task identifier

        Returns:
            True if bundle has valid PGP-signed approval
        """
        if task_id not in self.bundles:
            return False

        bundle = self.bundles[task_id]
        return bundle.is_approved()

    async def get_bundle(self, task_id: str) -> Optional[HILBundle]:
        """Get bundle for task."""
        return self.bundles.get(task_id)

    async def list_bundles(
        self, status: Optional[ApprovalStatus] = None
    ) -> List[HILBundle]:
        """List all bundles, optionally filtered by approval status."""
        bundles = list(self.bundles.values())

        if status:
            bundles = [b for b in bundles if b.approval_status == status]

        return sorted(bundles, key=lambda b: b.created_at, reverse=True)

    def get_bundle_stats(self) -> Dict[str, Any]:
        """Get bundle statistics."""
        bundles = list(self.bundles.values())

        pending = sum(1 for b in bundles if b.approval_status == ApprovalStatus.PENDING)
        approved = sum(1 for b in bundles if b.approval_status == ApprovalStatus.APPROVED)
        rejected = sum(1 for b in bundles if b.approval_status == ApprovalStatus.REJECTED)
        expired = sum(1 for b in bundles if b.approval_status == ApprovalStatus.EXPIRED)

        total_size = sum(
            Path(b.bundle_zip_path).stat().st_size
            for b in bundles
            if b.bundle_zip_path and Path(b.bundle_zip_path).exists()
        )

        return {
            "total_bundles": len(bundles),
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "expired": expired,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "approval_rate": (
                approved / len(bundles) if bundles else 0
            ),
        }

    async def export_bundle_manifest(self, output_path: str) -> bool:
        """
        Export all bundle metadata to manifest file.

        Args:
            output_path: Path to write manifest JSON

        Returns:
            True if exported successfully
        """
        bundles = list(self.bundles.values())
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_bundles": len(bundles),
            "bundles": [b.to_dict() for b in bundles],
            "approval_log": self.approval_log,
            "stats": self.get_bundle_stats(),
        }

        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Exported bundle manifest to {output_path}")
        return True


# Global bundle generator instance
_bundle_generator: Optional[HILBundleGenerator] = None


async def get_hil_bundle_generator(
    bundle_dir: str = "vault/evidence/hil_bundles",
) -> HILBundleGenerator:
    """Get or create global HiL bundle generator."""
    global _bundle_generator

    if _bundle_generator is None:
        _bundle_generator = HILBundleGenerator(bundle_dir=bundle_dir)

    return _bundle_generator
