"""Task 8 validation: Stability + Orchestration Layer."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.execution_orchestrator import ExecutionOrchestrator, JobState


def main() -> None:
    errors: list[str] = []
    orch = ExecutionOrchestrator()
    campaign = "campaign-test-001"

    # Submit 3 jobs
    job1 = orch.submit_job(campaign, "httpx", "api.example.com", max_attempts=3)
    job2 = orch.submit_job(campaign, "nuclei", "api.example.com", max_attempts=3)
    job3 = orch.submit_job(campaign, "ffuf", "api.example.com", max_attempts=1)

    # Mark job1 completed
    orch.mark_running(job1.job_id)
    orch.mark_completed(job1.job_id)

    # Mark job2 failed once -> should be RETRYING (attempt < max_attempts)
    orch.mark_running(job2.job_id)
    j2 = orch.mark_failed(job2.job_id, "connection timeout")
    if j2.state != JobState.RETRYING:
        errors.append(f"job2 should be RETRYING after first failure, got {j2.state}")

    # Mark job3 failed -> should be FAILED (max_attempts=1, so attempt==max_attempts after first fail)
    orch.mark_running(job3.job_id)
    j3 = orch.mark_failed(job3.job_id, "target unreachable")
    if j3.state != JobState.FAILED:
        errors.append(f"job3 should be FAILED after exhausting attempts, got {j3.state}")

    # Verify campaign state
    state = orch.get_campaign_state(campaign)
    if state["total"] != 3:
        errors.append(f"Expected total=3, got {state['total']}")
    if state["completed"] != 1:
        errors.append(f"Expected completed=1, got {state['completed']}")
    if state["retrying"] != 1:
        errors.append(f"Expected retrying=1, got {state['retrying']}")
    if state["failed"] != 1:
        errors.append(f"Expected failed=1, got {state['failed']}")

    # Verify retryable jobs
    retryable = orch.get_retryable_jobs()
    if len(retryable) != 1:
        errors.append(f"Expected 1 retryable job, got {len(retryable)}")
    elif retryable[0].job_id != job2.job_id:
        errors.append(f"Retryable job should be job2, got {retryable[0].job_id}")

    if errors:
        print("TASK 8 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 8 PASSED")


if __name__ == "__main__":
    main()
