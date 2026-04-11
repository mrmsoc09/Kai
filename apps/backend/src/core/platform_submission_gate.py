"""
Platform Submission Gate.

Implements the critical "HOLD-FOR-APPROVAL" logic that blocks all platform
submissions (HackerOne, Bugcrowd, Intigriti) until PGP-signed HiL approval
is received.

This is the final gating mechanism that makes platform submission technically
impossible without manual PGP signature from an authorized approver.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SubmissionPlatform(str, Enum):
    """Supported platforms for vulnerability submission."""
    HACKERONE = "hackerone"
    BUGCROWD = "bugcrowd"
    INTIGRITI = "intigriti"


class SubmissionGateStatus(str, Enum):
    """Submission gate status."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REQUIRES_APPROVAL = "requires_approval"


class SubmissionGateReason(str, Enum):
    """Reason for gate decision."""
    APPROVED_WITH_SIGNATURE = "approved_with_pgp_signature"
    BUNDLE_NOT_FOUND = "bundle_not_found"
    NO_PGP_SIGNATURE = "no_pgp_signature"
    SIGNATURE_EXPIRED = "pgp_signature_expired"
    NOT_APPROVED = "bundle_status_not_approved"
    APPROVAL_PENDING = "approval_pending"


class SubmissionGateCheck:
    """Result of submission gate check."""

    def __init__(
        self,
        task_id: str,
        status: SubmissionGateStatus,
        reason: SubmissionGateReason,
        allowed: bool,
        pgp_signature_valid: bool,
        approver_id: Optional[str] = None,
        signature_expiry: Optional[str] = None,
    ):
        self.task_id = task_id
        self.status = status
        self.reason = reason
        self.allowed = allowed
        self.pgp_signature_valid = pgp_signature_valid
        self.approver_id = approver_id
        self.signature_expiry = signature_expiry


class PlatformSubmissionGate:
    """
    Critical gating mechanism for platform submissions.

    Enforces:
    1. HiL bundle must exist
    2. Bundle must have valid PGP signature
    3. Signature must not be expired
    4. Bundle status must be APPROVED
    5. No workarounds: submission is technically impossible without all checks passing

    This is the final security gate before findings reach bug bounty platforms.
    """

    def __init__(self):
        """Initialize submission gate."""
        self._bundle_generator = None

    async def initialize(self) -> bool:
        """
        Initialize gate with bundle generator singleton.

        Returns:
            True if initialized successfully
        """
        try:
            from .generate_hil_bundle import get_hil_bundle_generator
            self._bundle_generator = await get_hil_bundle_generator()
            logger.info("✓ Platform Submission Gate initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Platform Submission Gate init failed: {str(e)}")
            return False

    # ═════════════════════════════════════════════════════════════════════════════
    # PRIMARY: Check if submission is allowed
    # ═════════════════════════════════════════════════════════════════════════════

    async def check_submission_allowed(
        self,
        task_id: str,
        platform: SubmissionPlatform,
    ) -> SubmissionGateCheck:
        """
        Check if submission to platform is allowed.

        CRITICAL: This is the final gate before platform submission.
        Returns False for ANY of:
        - No bundle found
        - No PGP signature
        - Signature expired
        - Bundle not approved

        Args:
            task_id: Task identifier
            platform: Target platform (hackerone, bugcrowd, intigriti)

        Returns:
            SubmissionGateCheck with detailed status
        """
        logger.warning(f"🚪 Platform Submission Gate Check: {platform.value}")
        logger.warning(f"   Task ID: {task_id}")

        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 1: Bundle must exist
        # ─────────────────────────────────────────────────────────────────────────

        if not self._bundle_generator:
            logger.error("❌ Bundle generator not initialized")
            return SubmissionGateCheck(
                task_id=task_id,
                status=SubmissionGateStatus.BLOCKED,
                reason=SubmissionGateReason.BUNDLE_NOT_FOUND,
                allowed=False,
                pgp_signature_valid=False,
            )

        bundle = await self._bundle_generator.get_bundle(task_id)

        if not bundle:
            logger.error(f"❌ No bundle found for {task_id}")
            logger.error(f"   → Submission BLOCKED")
            return SubmissionGateCheck(
                task_id=task_id,
                status=SubmissionGateStatus.BLOCKED,
                reason=SubmissionGateReason.BUNDLE_NOT_FOUND,
                allowed=False,
                pgp_signature_valid=False,
            )

        logger.info(f"   ✓ Bundle found: {bundle.bundle_id}")

        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 2: PGP Signature must exist
        # ─────────────────────────────────────────────────────────────────────────

        if not bundle.pgp_signature:
            logger.error(f"❌ No PGP signature on bundle for {task_id}")
            logger.error(f"   → Submission BLOCKED")
            logger.error(f"   → Operator must run: k1 approve {task_id} --pgp-sign <signature>")
            return SubmissionGateCheck(
                task_id=task_id,
                status=SubmissionGateStatus.BLOCKED,
                reason=SubmissionGateReason.NO_PGP_SIGNATURE,
                allowed=False,
                pgp_signature_valid=False,
            )

        logger.info(f"   ✓ PGP signature present (approver: {bundle.pgp_signature.approver_id})")

        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 3: Signature must be valid (not expired)
        # ─────────────────────────────────────────────────────────────────────────

        if not bundle.pgp_signature.is_valid():
            logger.error(f"❌ PGP signature expired for {task_id}")
            logger.error(f"   → Signature valid until: {bundle.pgp_signature.timestamp}")
            logger.error(f"   → Submission BLOCKED")
            logger.error(f"   → Operator must provide fresh signature: k1 approve {task_id} --pgp-sign <new_signature>")
            return SubmissionGateCheck(
                task_id=task_id,
                status=SubmissionGateStatus.BLOCKED,
                reason=SubmissionGateReason.SIGNATURE_EXPIRED,
                allowed=False,
                pgp_signature_valid=False,
                approver_id=bundle.pgp_signature.approver_id,
                signature_expiry=bundle.pgp_signature.timestamp,
            )

        logger.info(f"   ✓ PGP signature is valid and not expired")

        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 4: Bundle status must be APPROVED
        # ─────────────────────────────────────────────────────────────────────────

        if not bundle.is_approved():
            logger.error(f"❌ Bundle status not APPROVED for {task_id}")
            logger.error(f"   → Current status: {bundle.approval_status.value}")
            logger.error(f"   → Submission BLOCKED")
            return SubmissionGateCheck(
                task_id=task_id,
                status=SubmissionGateStatus.BLOCKED,
                reason=SubmissionGateReason.NOT_APPROVED,
                allowed=False,
                pgp_signature_valid=True,
                approver_id=bundle.pgp_signature.approver_id,
            )

        logger.info(f"   ✓ Bundle status is APPROVED")

        # ─────────────────────────────────────────────────────────────────────────
        # ALL CHECKS PASSED: Submission allowed
        # ─────────────────────────────────────────────────────────────────────────

        logger.warning(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.warning(f"✅ SUBMISSION ALLOWED: {task_id}")
        logger.warning(f"   Platform: {platform.value}")
        logger.warning(f"   Approver: {bundle.pgp_signature.approver_id}")
        logger.warning(f"   Signed: {bundle.pgp_signature.timestamp}")
        logger.warning(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return SubmissionGateCheck(
            task_id=task_id,
            status=SubmissionGateStatus.ALLOWED,
            reason=SubmissionGateReason.APPROVED_WITH_SIGNATURE,
            allowed=True,
            pgp_signature_valid=True,
            approver_id=bundle.pgp_signature.approver_id,
            signature_expiry=bundle.pgp_signature.timestamp,
        )

    # ═════════════════════════════════════════════════════════════════════════════
    # DECORATOR: Wrap submission calls with gate check
    # ═════════════════════════════════════════════════════════════════════════════

    async def submit_with_gate(
        self,
        task_id: str,
        platform: SubmissionPlatform,
        submission_fn,  # Async function that performs actual submission
        *submission_args,
        **submission_kwargs,
    ) -> Dict[str, Any]:
        """
        Execute submission only if gate check passes.

        Args:
            task_id: Task identifier
            platform: Target platform
            submission_fn: Async function to call for actual submission
            *submission_args: Arguments to pass to submission_fn
            **submission_kwargs: Keyword arguments to pass to submission_fn

        Returns:
            Result of submission_fn if allowed, error dict if blocked

        Raises:
            PermissionError if gate check fails (submission technically impossible)
        """
        # Run gate check
        gate_check = await self.check_submission_allowed(task_id, platform)

        if not gate_check.allowed:
            error_msg = (
                f"Submission blocked for {task_id}: {gate_check.reason.value}\n"
                f"Status: {gate_check.status.value}\n"
                f"Platform: {platform.value}"
            )
            logger.error(f"🔴 {error_msg}")

            # Raise exception to prevent submission from proceeding
            raise PermissionError(error_msg)

        # Gate check passed — proceed with submission
        logger.info(f"🚀 Proceeding with submission for {task_id}")

        try:
            result = await submission_fn(*submission_args, **submission_kwargs)
            logger.info(f"✅ Submission successful for {task_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Submission failed for {task_id}: {str(e)}")
            raise

    # ═════════════════════════════════════════════════════════════════════════════
    # LOGGING: Get gate status for UI/CLI display
    # ═════════════════════════════════════════════════════════════════════════════

    async def get_submission_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get current submission gate status for a task.

        Used to display in CLI/UI whether submission is ready.

        Args:
            task_id: Task identifier

        Returns:
            Dict with gate status, approval status, approver info
        """
        if not self._bundle_generator:
            return {"status": "error", "message": "Bundle generator not initialized"}

        bundle = await self._bundle_generator.get_bundle(task_id)

        if not bundle:
            return {
                "status": "blocked",
                "message": "No evidence bundle created",
                "can_submit": False,
            }

        return {
            "status": bundle.approval_status.value,
            "bundle_id": bundle.bundle_id,
            "created_at": bundle.created_at,
            "has_signature": bundle.pgp_signature is not None,
            "approver_id": bundle.pgp_signature.approver_id if bundle.pgp_signature else None,
            "signature_valid": bundle.pgp_signature.is_valid() if bundle.pgp_signature else False,
            "can_submit": bundle.is_approved(),
            "message": (
                "Ready for platform submission" if bundle.is_approved()
                else f"Awaiting approval (current status: {bundle.approval_status.value})"
            ),
        }


# ═════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═════════════════════════════════════════════════════════════════════════════

_gate: Optional[PlatformSubmissionGate] = None


async def get_platform_submission_gate() -> PlatformSubmissionGate:
    """Get or create global submission gate singleton."""
    global _gate

    if _gate is None:
        _gate = PlatformSubmissionGate()
        await _gate.initialize()

    return _gate
