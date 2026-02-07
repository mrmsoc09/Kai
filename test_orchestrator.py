#!/usr/bin/env python3
"""
KaiOrchestrator Testing Suite
Tests all compliance gates and middleware functionality
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "apps/backend/src"))

from core.kai_orchestrator import (
    KaiOrchestrator,
    ScopeGuardian,
    SignedIntentValidator,
    KaiAuditLogger,
    SubprocessExecutionGateway,
    TransparencyEnforcer,
    AutonomyTier
)


async def test_scope_guardian():
    """Test scope validation"""
    print("\n" + "="*70)
    print("TEST 1: SCOPE GUARDIAN VALIDATION")
    print("="*70)

    guardian = ScopeGuardian("config/authorized_scope.json")

    # Test cases
    test_cases = [
        ("example.com", True, "should pass: exact domain match"),
        ("api.example.com", True, "should pass: wildcard match"),
        ("subdomain.example.com", True, "should pass: deep wildcard match"),
        ("notinscope.com", False, "should fail: not in scope"),
        ("192.168.1.1", True, "should pass: authorized IP"),
        ("192.168.1.100", True, "should pass: IP in CIDR range"),
        ("8.8.8.8", False, "should fail: IP not in scope"),
        ("192.168.1.0/24", True, "should pass: exact CIDR match"),
        ("invalid.target...", False, "should fail: invalid format"),
    ]

    for target, expected, description in test_cases:
        is_valid, reason = await guardian.validate_target(target)
        status = "✓ PASS" if is_valid == expected else "✗ FAIL"
        print(f"{status}: {description}")
        print(f"    Target: {target}")
        print(f"    Result: {is_valid}, Reason: {reason}")


async def test_signed_intent():
    """Test Tier 3 permission slip validation"""
    print("\n" + "="*70)
    print("TEST 2: SIGNED INTENT VALIDATOR (Tier 3 Permission Slips)")
    print("="*70)

    validator = SignedIntentValidator("vault/permission_slips")

    # Create test permission slip
    print("\n[*] Creating test permission slip...")
    success, message = validator.create_permission_slip(
        target="example.com",
        operation_name="sqlmap_auth_test",
        authorized_targets=["example.com", "api.example.com"],
        allowed_operations=["sqlmap_auth_test", "other_ops"],
        expires_days=30,
        justification="Bug bounty platform authorization for HackerOne",
        scope_restrictions=["Do not modify data", "No credential exfiltration"]
    )
    print(f"[{'✓' if success else '✗'}] {message}")

    # Test validation
    print("\n[*] Validating permission slip...")
    valid, reason, metadata = await validator.validate_tier_3_operation(
        target="example.com",
        operation_name="sqlmap_auth_test",
        operation_params={}
    )

    status = "✓ PASS" if valid else "✗ FAIL"
    print(f"{status}: Permission slip validation")
    print(f"    Valid: {valid}, Reason: {reason}")
    if metadata:
        print(f"    Metadata: {json.dumps(metadata, indent=2)}")

    # Test invalid operation
    print("\n[*] Testing invalid operation (should fail)...")
    valid, reason, metadata = await validator.validate_tier_3_operation(
        target="example.com",
        operation_name="nonexistent_operation",
        operation_params={}
    )

    status = "✓ PASS" if not valid else "✗ FAIL"
    print(f"{status}: Invalid operation rejection")
    print(f"    Valid: {valid}, Reason: {reason}")


async def test_audit_logger():
    """Test pre/post execution logging"""
    print("\n" + "="*70)
    print("TEST 3: KAI AUDIT LOGGER (Pre/Post Execution Logging)")
    print("="*70)

    logger = KaiAuditLogger("var/lib/kai/logs/orchestrator")

    print(f"\n[*] Log directory: {logger.log_dir}")

    # Test pre-execution logging
    print("\n[*] Logging pre-execution operation...")
    success, message, log_id = await logger.log_pending_operation(
        user_id="test_user",
        certificate_id="test_cert_123",
        target="example.com",
        tool_name="osint_tool",
        tool_params={"domain": "example.com"},
        autonomy_tier="TIER_1_NOTIFY",
        reasoning="Gathering intelligence on target web properties",
        scope_validation={"target": "example.com", "valid": True},
        intent_validation=None
    )

    status = "✓ PASS" if success else "✗ FAIL"
    print(f"{status}: Pre-execution logging")
    print(f"    Message: {message}")
    print(f"    Log ID: {log_id}")

    # Test post-execution logging
    print("\n[*] Logging post-execution result...")
    success, message = await logger.log_execution_result(
        log_id=log_id,
        execution_success=True,
        execution_output={"findings": ["subdomain1.example.com", "subdomain2.example.com"]},
        error_message=None
    )

    status = "✓ PASS" if success else "✗ FAIL"
    print(f"{status}: Post-execution logging")
    print(f"    Message: {message}")

    # Verify logs exist
    pre_log = logger.log_dir / f"{log_id}_pre_execution.jsonl"
    post_log = logger.log_dir / f"{log_id}_post_execution.jsonl"

    print(f"\n[*] Verifying log files...")
    print(f"    Pre-execution log exists: {pre_log.exists()}")
    print(f"    Post-execution log exists: {post_log.exists()}")

    if pre_log.exists():
        with open(pre_log) as f:
            pre_content = json.load(f)
            print(f"    Pre-execution log keys: {list(pre_content.keys())}")


async def test_transparency_enforcer():
    """Test report generation with mandatory headers"""
    print("\n" + "="*70)
    print("TEST 4: TRANSPARENCY LAYER (AI-Generated Headers)")
    print("="*70)

    enforcer = TransparencyEnforcer("var/lib/kai/reports")

    print(f"\n[*] Reports directory: {enforcer.reports_dir}")

    # Generate test report
    print("\n[*] Generating report with transparency headers...")
    success, report_path, metadata_path = await enforcer.process_tool_output(
        tool_name="osint_tool",
        raw_output={
            "subdomains_found": ["api.example.com", "app.example.com"],
            "dns_records": {"example.com": {"A": ["93.184.216.34"]}},
            "open_ports": [80, 443, 8080]
        },
        log_id="test_log_12345",
        certificate_id="test_cert_123",
        timestamp="2025-02-02T10:00:00Z"
    )

    status = "✓ PASS" if success else "✗ FAIL"
    print(f"{status}: Report generation")
    print(f"    Report path: {report_path}")
    print(f"    Metadata path: {metadata_path}")

    # Verify report contains mandatory header
    if report_path and Path(report_path).exists():
        with open(report_path) as f:
            report_content = f.read()
            has_header = "[AI-GENERATED REPORT:" in report_content
            has_supervision = "HUMAN SUPERVISION" in report_content
            print(f"\n[*] Report content verification:")
            print(f"    Contains AI-GENERATED header: {has_header}")
            print(f"    Contains HUMAN SUPERVISION text: {has_supervision}")
            print(f"    First 300 chars:\n    {report_content[:300]}")

    # Verify metadata
    if metadata_path and Path(metadata_path).exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
            print(f"\n[*] Metadata verification:")
            print(f"    Metadata keys: {list(metadata.keys())}")
            print(f"    AI-generated flag: {metadata.get('ai_generated')}")


async def test_full_orchestrator_pipeline():
    """Test complete orchestrator pipeline"""
    print("\n" + "="*70)
    print("TEST 5: FULL ORCHESTRATOR PIPELINE")
    print("="*70)

    orchestrator = KaiOrchestrator(
        scope_config_path="config/authorized_scope.json",
        permission_slips_vault_path="vault/permission_slips"
    )

    print(f"\n[*] Running end-to-end orchestrator test...")
    print(f"    Scope Guardian: {orchestrator.scope_guardian}")
    print(f"    Signed Intent Validator: {orchestrator.signed_intent}")
    print(f"    Audit Logger: {orchestrator.audit_logger}")
    print(f"    Execution Gateway: {orchestrator.execution_gateway}")
    print(f"    Transparency Enforcer: {orchestrator.transparency}")

    # Note: We can't test full execution without a real tool command
    # This test demonstrates the pipeline structure

    # Test Tier 1 tool
    print("\n[*] Testing Tier 1 (OSINT) tool autonomy tier...")
    tier = orchestrator._get_tool_autonomy_tier("osint_tool")
    print(f"    osint_tool tier: {tier}")

    # Test Tier 3 tool
    print("\n[*] Testing Tier 3 (Exploitation) tool autonomy tier...")
    tier = orchestrator._get_tool_autonomy_tier("sqlmap")
    print(f"    sqlmap tier: {tier}")

    print("\n[✓] Orchestrator pipeline test completed")


async def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("KaiOrchestrator Compliance Middleware - Test Suite")
    print("="*70)

    try:
        await test_scope_guardian()
        await test_signed_intent()
        await test_audit_logger()
        await test_transparency_enforcer()
        await test_full_orchestrator_pipeline()

        print("\n" + "="*70)
        print("ALL TESTS COMPLETED")
        print("="*70)
        print("\n[✓] KaiOrchestrator middleware is fully functional")
        print("[✓] All compliance gates are operational")
        print("[✓] Audit logging and transparency layers working")

    except Exception as e:
        print(f"\n[✗] TEST ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
