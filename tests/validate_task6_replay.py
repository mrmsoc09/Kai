"""Task 6 validation: Replay + Proof System."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.replay_service import ReplayPackage, ReplayService


def main() -> None:
    errors: list[str] = []
    svc = ReplayService()

    # Build a mock evidence-like object with 3 of 5 replay fields set
    class MockEvidence:
        id = "ev-001"
        replay_request_response_uri = "s3://bucket/req_resp.har"
        replay_command_transcript_uri = "s3://bucket/transcript.txt"
        replay_screen_recording_uri = "s3://bucket/recording.mp4"
        replay_reproduction_steps = None
        replay_terminal_ref = None

    pkg = svc.build_replay_package(MockEvidence())

    if not pkg.is_reproducible:
        errors.append("Package with 3 artifacts should be reproducible")

    expected_score = 3 / 5  # 0.6
    if abs(pkg.completeness_score - expected_score) > 0.001:
        errors.append(
            f"Expected completeness_score={expected_score}, got {pkg.completeness_score}"
        )

    # Assess proof completeness
    assessment = svc.assess_proof_completeness([pkg])
    if assessment["total_evidence"] != 1:
        errors.append(f"Expected total_evidence=1, got {assessment['total_evidence']}")
    if assessment["reproducible_count"] != 1:
        errors.append(f"Expected reproducible_count=1, got {assessment['reproducible_count']}")
    if not assessment["proof_ready"]:
        errors.append("proof_ready should be True (completeness=0.6, reproducible=True)")

    # Test a package with only 2 fields (below 0.6 threshold)
    class MockEvidence2:
        id = "ev-002"
        replay_request_response_uri = "s3://bucket/req.har"
        replay_command_transcript_uri = "s3://bucket/cmd.txt"
        replay_screen_recording_uri = None
        replay_reproduction_steps = None
        replay_terminal_ref = None

    pkg2 = svc.build_replay_package(MockEvidence2())
    if not pkg2.is_reproducible:
        errors.append("Package with 2 artifacts should be reproducible")
    if pkg2.completeness_score >= 0.6:
        errors.append(f"2/5 completeness should be < 0.6, got {pkg2.completeness_score}")

    assessment2 = svc.assess_proof_completeness([pkg2])
    if assessment2["proof_ready"]:
        errors.append("proof_ready should be False (completeness < 0.6)")

    # Empty package
    class MockEvidence3:
        id = "ev-003"
        replay_request_response_uri = None
        replay_command_transcript_uri = None
        replay_screen_recording_uri = None
        replay_reproduction_steps = None
        replay_terminal_ref = None

    pkg3 = svc.build_replay_package(MockEvidence3())
    if pkg3.is_reproducible:
        errors.append("Package with no artifacts should NOT be reproducible")

    if errors:
        print("TASK 6 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 6 PASSED")


if __name__ == "__main__":
    main()
