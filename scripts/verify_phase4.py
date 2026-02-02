#!/usr/bin/env python3
"""Phase 4: Vulnerability Detection Verification Script."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_detection_imports():
    """Test that detection module can be imported."""
    try:
        from modules.detection import (
            FindingDeduplicator,
            EvidenceTracker,
            FindingAnalyzer,
            NucleiScanner,
        )

        print("[✓] Detection Module Imports............. PASS")
        return True
    except ImportError as e:
        print(f"[✗] Detection Module Imports............. FAIL ({e})")
        return False


def test_finding_deduplicator():
    """Test finding deduplication engine."""
    try:
        from modules.detection import FindingDeduplicator

        dedup = FindingDeduplicator()

        # Create test findings
        finding1 = {
            "url": "https://example.com/api",
            "vulnerability_type": "sql_injection",
            "severity": "high",
            "parameter": "id",
            "description": "SQL injection in id parameter",
        }

        finding2 = {
            "url": "https://example.com/api",
            "vulnerability_type": "sql_injection",
            "severity": "high",
            "parameter": "id",
            "description": "SQL injection in id parameter",
        }

        finding3 = {
            "url": "https://example.com/search",
            "vulnerability_type": "cross_site_scripting",
            "severity": "medium",
            "parameter": "q",
            "description": "Stored XSS in search",
        }

        findings = [finding1, finding2, finding3]

        # Test deduplication
        result = dedup.deduplicate(findings, strategy="multi")

        if result["unique_count"] != 2:
            print(f"[✗] Finding Deduplicator................ FAIL (expected 2 unique, got {result['unique_count']})")
            return False

        if result["duplicate_count"] != 1:
            print(f"[✗] Finding Deduplicator................ FAIL (expected 1 duplicate, got {result['duplicate_count']})")
            return False

        # Test hash computation
        hash_val = dedup.compute_finding_hash(finding1, "primary")
        if not hash_val or len(hash_val) != 64:
            print("[✗] Finding Deduplicator................ FAIL (invalid hash)")
            return False

        print("[✓] Finding Deduplicator................ PASS")
        return True
    except Exception as e:
        print(f"[✗] Finding Deduplicator................ FAIL ({e})")
        return False


def test_evidence_tracker():
    """Test evidence integrity tracking."""
    try:
        from modules.detection import EvidenceTracker

        tracker = EvidenceTracker()

        # Record evidence
        evidence1 = tracker.record_evidence(
            evidence_type="scan_output",
            content={"url": "https://example.com", "status": "200"},
            source="nuclei",
            finding_id="finding_1",
        )

        if "id" not in evidence1:
            print("[✗] Evidence Tracker..................... FAIL (no ID generated)")
            return False

        if "chain_hash" not in evidence1:
            print("[✗] Evidence Tracker..................... FAIL (no chain hash)")
            return False

        # Verify integrity
        verification = tracker.verify_evidence_integrity(evidence1.get("id"))
        if not verification.get("valid"):
            print("[✗] Evidence Tracker..................... FAIL (invalid evidence)")
            return False

        # Record another piece of evidence
        evidence2 = tracker.record_evidence(
            evidence_type="analysis",
            content={"confidence": 0.95},
            source="analyzer",
            finding_id="finding_1",
        )

        # Verify chain
        if evidence2.get("previous_hash") != evidence1.get("chain_hash"):
            print("[✗] Evidence Tracker..................... FAIL (chain broken)")
            return False

        print("[✓] Evidence Tracker..................... PASS")
        return True
    except Exception as e:
        print(f"[✗] Evidence Tracker..................... FAIL ({e})")
        return False


def test_finding_analyzer():
    """Test finding analysis and severity assessment."""
    try:
        from modules.detection import FindingAnalyzer

        analyzer = FindingAnalyzer()

        finding = {
            "id": "test_finding_1",
            "vulnerability_type": "sql_injection",
            "description": "SQL injection vulnerability found",
            "impact": {
                "confidentiality": "high",
                "integrity": "high",
                "availability": "low",
            },
            "requires_authentication": False,
            "requires_user_interaction": False,
        }

        analysis = analyzer.analyze_finding(finding)

        if "cvss_score" not in analysis:
            print("[✗] Finding Analyzer..................... FAIL (no CVSS score)")
            return False

        if "severity" not in analysis:
            print("[✗] Finding Analyzer..................... FAIL (no severity)")
            return False

        # CVSS score should be between 0-10
        if not (0 <= analysis["cvss_score"] <= 10):
            print("[✗] Finding Analyzer..................... FAIL (invalid CVSS score)")
            return False

        # SQL injection should have high exploitability
        if analysis["exploitability_score"] < 0.8:
            print("[✗] Finding Analyzer..................... FAIL (low exploitability for SQL injection)")
            return False

        print("[✓] Finding Analyzer..................... PASS")
        return True
    except Exception as e:
        print(f"[✗] Finding Analyzer..................... FAIL ({e})")
        return False


def test_nuclei_scanner():
    """Test Nuclei scanner integration."""
    try:
        from modules.detection import NucleiScanner

        scanner = NucleiScanner()

        # Validate setup
        validation = scanner.validate_nuclei_setup()

        if "nuclei_path" not in validation:
            print("[✗] Nuclei Scanner....................... FAIL (no path)")
            return False

        # Even if nuclei is not installed, we test the class structure
        stats = scanner.get_scan_stats()
        if stats["total_scans"] != 0:
            print("[✗] Nuclei Scanner....................... FAIL (should have 0 initial scans)")
            return False

        print("[✓] Nuclei Scanner....................... PASS (setup: installed={}, templates={})".format(
            validation.get("is_installed", False),
            validation.get("templates_available", False),
        ))
        return True
    except Exception as e:
        print(f"[✗] Nuclei Scanner....................... FAIL ({e})")
        return False


def test_deduplication_strategies():
    """Test different deduplication strategies."""
    try:
        from modules.detection import FindingDeduplicator

        dedup = FindingDeduplicator()

        findings = [
            {
                "url": "https://example.com/api",
                "vulnerability_type": "sql_injection",
                "severity": "high",
            },
            {
                "url": "https://example.com/api",
                "vulnerability_type": "sql_injection",
                "severity": "high",
            },
            {
                "url": "https://example.com/search",
                "vulnerability_type": "xss",
                "severity": "medium",
            },
        ]

        for strategy in ["exact", "shallow", "fuzzy", "multi"]:
            result = dedup.deduplicate(findings, strategy=strategy)
            if "unique_findings" not in result:
                print(f"[✗] Dedup Strategies ({strategy})......... FAIL (no results)")
                return False

        print("[✓] Dedup Strategies (all)............... PASS")
        return True
    except Exception as e:
        print(f"[✗] Dedup Strategies..................... FAIL ({e})")
        return False


def test_finding_prioritization():
    """Test finding prioritization by different strategies."""
    try:
        from modules.detection import FindingAnalyzer

        analyzer = FindingAnalyzer()

        findings = [
            {
                "id": "f1",
                "vulnerability_type": "sql_injection",
                "impact": {"confidentiality": "high", "integrity": "high", "availability": "low"},
            },
            {
                "id": "f2",
                "vulnerability_type": "info_disclosure",
                "impact": {"confidentiality": "medium", "integrity": "low", "availability": "none"},
            },
            {
                "id": "f3",
                "vulnerability_type": "remote_code_execution",
                "impact": {"confidentiality": "critical", "integrity": "critical", "availability": "critical"},
            },
        ]

        prioritized = analyzer.prioritize_findings(findings, strategies=["severity", "exploitability"])

        if "severity" not in prioritized or "exploitability" not in prioritized:
            print("[✗] Finding Prioritization............... FAIL (missing strategies)")
            return False

        # Check severity prioritization
        severity_findings = prioritized["severity"]
        if len(severity_findings) == 0:
            print("[✗] Finding Prioritization............... FAIL (no results)")
            return False

        print("[✓] Finding Prioritization............... PASS")
        return True
    except Exception as e:
        print(f"[✗] Finding Prioritization............... FAIL ({e})")
        return False


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("PHASE 4: VULNERABILITY DETECTION VERIFICATION")
    print("=" * 70 + "\n")

    tests = [
        ("Detection Module Imports", test_detection_imports),
        ("Finding Deduplicator", test_finding_deduplicator),
        ("Evidence Tracker", test_evidence_tracker),
        ("Finding Analyzer", test_finding_analyzer),
        ("Nuclei Scanner", test_nuclei_scanner),
        ("Dedup Strategies", test_deduplication_strategies),
        ("Finding Prioritization", test_finding_prioritization),
    ]

    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append(result)
        print()

    # Summary
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0

    print("=" * 70)
    print(f"PHASE 4 VERIFICATION: {passed}/{total} checks passed ({percentage:.0f}%)")
    print("=" * 70 + "\n")

    if all(results):
        print("✓ All Phase 4 checks passed!")
        print("✓ Vulnerability detection module is fully functional")
        print("✓ Finding deduplication, analysis, and tracking ready\n")
        return 0
    else:
        print("✗ Some checks failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
