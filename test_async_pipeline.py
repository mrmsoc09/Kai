#!/usr/bin/env python3
"""
Test script for K1 Async Evidence Generation Pipeline.

This script demonstrates:
1. Finding detection and status tracking
2. Non-blocking background task dispatch
3. Concurrent processing of multiple findings
4. Graceful shutdown handling
"""

import asyncio
import sys
import logging

# Setup Python path for imports
sys.path.insert(0, '/home/k1-admin/Kai/apps/backend/src')

from core.finding_status_tracker import (
    get_finding_status_tracker,
    FindingStatusEnum,
)
from core.background_evidence_dispatcher import get_background_evidence_dispatcher
from core.graceful_shutdown_handler import get_graceful_shutdown_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def simulate_evidence_collection(
    task_id: str,
    target_url: str,
    vulnerability_type: str,
    severity: str,
    tool_name: str,
) -> dict:
    """Simulate evidence collection (record, script gen, bundling)."""
    logger.info(f"  📋 [BG] Starting evidence collection for {task_id}")

    # Simulate time-consuming operations
    logger.info(f"  🎥 [BG] Recording vulnerability reproduction...")
    await asyncio.sleep(2)  # Simulate recording

    logger.info(f"  🔧 [BG] Generating reproduction scripts...")
    await asyncio.sleep(1)  # Simulate script generation

    logger.info(f"  📦 [BG] Creating HiL Review Bundle...")
    await asyncio.sleep(1)  # Simulate bundling

    logger.info(f"  ✅ [BG] Evidence collection complete for {task_id}")

    return {
        "status": "complete",
        "task_id": task_id,
        "evidence_files": ["recording.webm", "repro.sh", "repro.py", "exploit.py"],
    }


async def test_async_pipeline():
    """Test async evidence generation pipeline."""
    print("\n" + "="*70)
    print("K1 ASYNC EVIDENCE GENERATION PIPELINE TEST")
    print("="*70 + "\n")

    # Initialize systems
    status_tracker = await get_finding_status_tracker()
    dispatcher = get_background_evidence_dispatcher()
    shutdown_handler = get_graceful_shutdown_handler()

    await shutdown_handler.initialize()

    try:
        print("[TEST 1] Finding Detection & Status Tracking")
        print("-" * 70)

        # Simulate finding #1 detected
        logger.info("🔍 Finding #1 detected: SQL Injection")
        finding1 = await status_tracker.create_finding(
            task_id="task_abc123",
            target_url="https://example.com/admin",
            vulnerability_type="SQL Injection",
            severity="CRITICAL",
            tool_name="nuclei",
        )
        print(f"✓ Finding created: {finding1.finding_id}")
        print(f"  Status: {finding1.status.value}\n")

        # Simulate finding #2 detected
        logger.info("🔍 Finding #2 detected: XSS Vulnerability")
        finding2 = await status_tracker.create_finding(
            task_id="task_def456",
            target_url="https://example.com/search",
            vulnerability_type="Cross-Site Scripting (XSS)",
            severity="HIGH",
            tool_name="burp",
        )
        print(f"✓ Finding created: {finding2.finding_id}")
        print(f"  Status: {finding2.status.value}\n")

        # Simulate finding #3 detected
        logger.info("🔍 Finding #3 detected: Path Traversal")
        finding3 = await status_tracker.create_finding(
            task_id="task_ghi789",
            target_url="https://example.com/upload",
            vulnerability_type="Path Traversal",
            severity="HIGH",
            tool_name="nuclei",
        )
        print(f"✓ Finding created: {finding3.finding_id}")
        print(f"  Status: {finding3.status.value}\n")

        print("[TEST 2] Non-Blocking Background Task Dispatch")
        print("-" * 70)

        # Dispatch evidence collection (should return immediately)
        print("⏱️  Dispatching evidence collection tasks...\n")

        start_time = asyncio.get_event_loop().time()

        # Dispatch finding #1
        logger.info("📤 Dispatching Finding #1 to background...")

        # Define evidence collection closure
        async def collect_evidence_1():
            return await simulate_evidence_collection(
                task_id="task_abc123",
                target_url="https://example.com/admin",
                vulnerability_type="SQL Injection",
                severity="CRITICAL",
                tool_name="nuclei",
            )

        task1_id = await dispatcher.dispatch_evidence_collection(
            finding_id=finding1.finding_id,
            task_id="task_abc123",
            target_url="https://example.com/admin",
            vulnerability_type="SQL Injection",
            severity="CRITICAL",
            tool_name="nuclei",
            evidence={},
            evidence_fn=collect_evidence_1,
            status_tracker=status_tracker,
        )
        dispatch_time_1 = asyncio.get_event_loop().time() - start_time
        print(f"✓ Finding #1 dispatched in {dispatch_time_1:.3f}s: {task1_id}\n")

        # Dispatch finding #2
        logger.info("📤 Dispatching Finding #2 to background...")
        start = asyncio.get_event_loop().time()

        async def collect_evidence_2():
            return await simulate_evidence_collection(
                task_id="task_def456",
                target_url="https://example.com/search",
                vulnerability_type="Cross-Site Scripting (XSS)",
                severity="HIGH",
                tool_name="burp",
            )

        task2_id = await dispatcher.dispatch_evidence_collection(
            finding_id=finding2.finding_id,
            task_id="task_def456",
            target_url="https://example.com/search",
            vulnerability_type="Cross-Site Scripting (XSS)",
            severity="HIGH",
            tool_name="burp",
            evidence={},
            evidence_fn=collect_evidence_2,
            status_tracker=status_tracker,
        )
        dispatch_time_2 = asyncio.get_event_loop().time() - start
        print(f"✓ Finding #2 dispatched in {dispatch_time_2:.3f}s: {task2_id}\n")

        # Dispatch finding #3
        logger.info("📤 Dispatching Finding #3 to background...")
        start = asyncio.get_event_loop().time()

        async def collect_evidence_3():
            return await simulate_evidence_collection(
                task_id="task_ghi789",
                target_url="https://example.com/upload",
                vulnerability_type="Path Traversal",
                severity="HIGH",
                tool_name="nuclei",
            )

        task3_id = await dispatcher.dispatch_evidence_collection(
            finding_id=finding3.finding_id,
            task_id="task_ghi789",
            target_url="https://example.com/upload",
            vulnerability_type="Path Traversal",
            severity="HIGH",
            tool_name="nuclei",
            evidence={},
            evidence_fn=collect_evidence_3,
            status_tracker=status_tracker,
        )
        dispatch_time_3 = asyncio.get_event_loop().time() - start
        print(f"✓ Finding #3 dispatched in {dispatch_time_3:.3f}s: {task3_id}\n")

        print("[TEST 3] Concurrent Background Task Processing")
        print("-" * 70)

        # Check active tasks
        active = await dispatcher.get_active_tasks()
        print(f"Active background tasks: {len(active)}")
        for name in active:
            print(f"  • {name}")
        print()

        # Wait for all background tasks to complete
        print("⏳ Waiting for background tasks to complete...\n")
        results = await dispatcher.wait_all_tasks(timeout_seconds=60)

        print(f"\n✓ All {len(results)} background tasks completed!")
        for i, result in enumerate(results, 1):
            print(f"  Task #{i}: {result}")
        print()

        print("[TEST 4] Final Status Check")
        print("-" * 70)

        # Get final statistics
        stats = await status_tracker.get_stats()
        print("Finding Status Summary:")
        print(f"  Total findings: {stats['total_findings']}")
        print(f"  In progress: {stats['in_progress']}")
        print(f"  By status:")
        for status_name, count in stats['by_status'].items():
            print(f"    • {status_name}: {count}")
        print()

        # Get findings by specific status
        awaiting = await status_tracker.get_findings_by_status(FindingStatusEnum.AWAITING_REVIEW)
        print(f"Findings awaiting review: {len(awaiting)}")
        for finding in awaiting:
            print(f"  • {finding.finding_id}: {finding.vulnerability_type} @ {finding.target_url}")
        print()

        print("[TEST 5] Approval Simulation")
        print("-" * 70)

        # Simulate approver approving finding #1
        logger.info(f"👤 Approver signing finding {finding1.finding_id}...")
        await status_tracker.approve_finding(
            finding_id=finding1.finding_id,
            approver_id="admin",
        )
        print(f"✓ Finding {finding1.finding_id} approved by admin\n")

        # Check updated status
        updated_finding1 = await status_tracker.get_finding(finding1.finding_id)
        print(f"Updated status: {updated_finding1.status.value}")
        print(f"Approved by: {updated_finding1.approver_id}")
        print()

        print("="*70)
        print("✅ ASYNC PIPELINE TEST COMPLETE")
        print("="*70 + "\n")

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test runner."""
    try:
        success = await test_async_pipeline()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
