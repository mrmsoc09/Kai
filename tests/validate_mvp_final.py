"""Final MVP validation: End-to-end smoke test across all 8 tasks."""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))


async def run_mvp_flow() -> list[str]:
    errors: list[str] = []

    # --- Step 1: Ingest a program (Task 4) ---
    from core.program_ingestion_service import ProgramIngestionService

    ingestion_svc = ProgramIngestionService()
    payload = {
        "handle": "acme-corp",
        "platform": "hackerone",
        "in_scope": [
            {"asset_identifier": "api.acme.com", "asset_type": "URL"},
            {"asset_identifier": "www.acme.com", "asset_type": "URL"},
            {"asset_identifier": "*.acme.com", "asset_type": "WILDCARD"},
        ],
        "out_of_scope": [
            {"asset_identifier": "admin.acme.com", "asset_type": "URL"},
        ],
    }
    program = ingestion_svc.ingest_from_hackerone_payload(payload)

    # --- Step 2: Derive scan targets ---
    targets = ingestion_svc.derive_scan_targets(program)
    if len(targets) < 2:
        errors.append(f"Expected at least 2 targets, got {len(targets)}")

    # --- Step 3: Check each target against scope (Task 1) ---
    from core.scope_ingestion_service import NormalizedScope, ScopeEnforcementGate

    scope = NormalizedScope(
        allowed=["acme.com", "*.acme.com"],
        denied=["admin.acme.com"],
    )
    gate = ScopeEnforcementGate()

    in_scope_targets = [t for t in targets if gate.check_target(t, scope)]
    if "admin.acme.com" in in_scope_targets:
        errors.append("admin.acme.com should be blocked by denylist")
    if not in_scope_targets:
        errors.append("No in-scope targets found")

    # --- Step 4: Check tool governance for the scan tool (Task 3) ---
    from core.tool_governance_service import ToolGovernanceService

    gov_svc = ToolGovernanceService()
    result = gov_svc.check_tool_authorization("httpx", "campaign-001")
    if not result.allowed:
        errors.append("httpx (Band 1) should be auto-approved")

    result_ffuf = gov_svc.check_tool_authorization("ffuf", "campaign-001")
    if result_ffuf.allowed:
        errors.append("ffuf (Band 2) should require approval without gate")

    # --- Step 5: Apply execution safety (Task 2) ---
    from core.execution_safety import ExecutionSafetyConfig, ExecutionSafetyLayer

    safety = ExecutionSafetyLayer(ExecutionSafetyConfig(rate_limit_rps=100, max_retries=1))
    await safety.check_rate_limit("httpx")  # should not raise

    # --- Step 6: Submit job to orchestrator (Task 8) ---
    from core.execution_orchestrator import ExecutionOrchestrator, JobState

    orch = ExecutionOrchestrator()
    job = orch.submit_job("campaign-001", "httpx", in_scope_targets[0])
    orch.mark_running(job.job_id)
    orch.mark_completed(job.job_id)

    state = orch.get_campaign_state("campaign-001")
    if state["completed"] != 1:
        errors.append(f"Expected 1 completed job, got {state['completed']}")

    # --- Step 7: Simulate finding discovery ---
    finding = {
        "id": "finding-001",
        "title": "SQL Injection in Login API",
        "description": "The /login endpoint is vulnerable to SQL injection via the username param.",
        "asset": in_scope_targets[0],
        "endpoint": f"https://{in_scope_targets[0]}/login",
        "vulnerability_type": "SQL Injection",
        "vuln_type": "sql_injection",
        "parameter": "username",
        "cvss_score": 9.8,
        "impact": "Full database compromise possible.",
        "steps_to_reproduce": "1. POST to /login with username=' OR 1=1--\n2. Observe 200 response",
    }

    # --- Step 8: Check for duplicates (Task 7) ---
    from core.dedup_service import DeduplicationService

    dedup = DeduplicationService()
    check1 = await dedup.check_duplicate(finding, "campaign-001")
    if check1.is_duplicate:
        errors.append("First finding should not be a duplicate")

    await dedup.register_finding(finding, "campaign-001")

    check2 = await dedup.check_duplicate(finding, "campaign-001")
    if not check2.is_duplicate:
        errors.append("Second identical finding should be flagged as duplicate")

    # --- Step 9: Build replay package (Task 6) ---
    from core.replay_service import ReplayService

    class MockEvidence:
        id = "ev-001"
        replay_request_response_uri = "s3://evidence/sqli-req.har"
        replay_command_transcript_uri = "s3://evidence/sqli-transcript.txt"
        replay_screen_recording_uri = "s3://evidence/sqli-recording.mp4"
        replay_reproduction_steps = "1. Send SQLi payload\n2. Check response"
        replay_terminal_ref = None

    replay_svc = ReplayService()
    pkg = replay_svc.build_replay_package(MockEvidence())
    assessment = replay_svc.assess_proof_completeness([pkg])
    if not assessment["proof_ready"]:
        errors.append("Proof should be ready (4/5 artifacts, completeness=0.8)")

    # --- Step 10: Generate report (Task 5) ---
    from core.report_generation_service import ReportGenerationService

    report_svc = ReportGenerationService()
    report = report_svc.generate_hackerone_report(
        finding,
        evidence_list=[{"artifact_uri": "s3://evidence/sqli-req.har", "evidence_type": "http_trace"}],
    )
    if "## Summary" not in report:
        errors.append("Report missing Summary section")
    if "## Steps to Reproduce" not in report:
        errors.append("Report missing Steps to Reproduce section")
    if "SQL Injection" not in report:
        errors.append("Report should mention the vulnerability type")

    return errors


def main() -> None:
    errors = asyncio.run(run_mvp_flow())
    if errors:
        print("MVP VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("MVP VALIDATION PASSED")


if __name__ == "__main__":
    main()
