#!/usr/bin/env python3
"""Phase 5: Patch Engine Verification Script."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_patching_imports():
    """Test that patching module can be imported."""
    try:
        from modules.patching import (
            PatchGenerator,
            PackageAnalyzer,
            PatchValidator,
            RemediationEngine,
        )

        print("[✓] Patching Module Imports............. PASS")
        return True
    except ImportError as e:
        print(f"[✗] Patching Module Imports............. FAIL ({e})")
        return False


def test_patch_generator():
    """Test patch generation."""
    try:
        from modules.patching import PatchGenerator

        generator = PatchGenerator()

        finding = {
            "id": "test_finding_1",
            "vulnerability_type": "sql_injection",
            "severity": "high",
            "description": "SQL injection vulnerability",
        }

        patch = generator.generate_patch(finding)

        if "remediation_steps" not in patch:
            print("[✗] Patch Generator..................... FAIL (no remediation steps)")
            return False

        if not patch.get("remediation_steps"):
            print("[✗] Patch Generator..................... FAIL (empty steps)")
            return False

        if patch.get("complexity") not in ["easy", "medium", "hard"]:
            print("[✗] Patch Generator..................... FAIL (invalid complexity)")
            return False

        print("[✓] Patch Generator..................... PASS")
        return True
    except Exception as e:
        print(f"[✗] Patch Generator..................... FAIL ({e})")
        return False


def test_package_analyzer():
    """Test package analysis."""
    try:
        from modules.patching import PackageAnalyzer

        analyzer = PackageAnalyzer()

        # Test Django analysis (known vulnerable package)
        analysis = analyzer.analyze_package("django", "2.2.27")

        if not analysis.get("is_vulnerable"):
            print("[✗] Package Analyzer.................... FAIL (should detect Django 2.2.27 as vulnerable)")
            return False

        # Test non-vulnerable package
        analysis2 = analyzer.analyze_package("requests", "2.28.0")
        if analysis2.get("is_vulnerable"):
            print("[✗] Package Analyzer.................... FAIL (should not flag recent version as vulnerable)")
            return False

        print("[✓] Package Analyzer.................... PASS")
        return True
    except Exception as e:
        print(f"[✗] Package Analyzer.................... FAIL ({e})")
        return False


def test_patch_validator():
    """Test patch validation."""
    try:
        from modules.patching import PatchValidator

        validator = PatchValidator()

        patch = {
            "finding_id": "test_finding_1",
            "vulnerability_type": "sql_injection",
            "description": "SQL injection fix",
            "remediation_steps": ["Use parameterized queries"],
            "code_examples": {
                "vulnerable": 'query = f"SELECT * FROM users WHERE id = {user_id}"',
                "patched": 'query = "SELECT * FROM users WHERE id = %s"',
            },
        }

        validation = validator.validate_patch(patch)

        if "is_valid" not in validation:
            print("[✗] Patch Validator..................... FAIL (no validation result)")
            return False

        if "confidence_score" not in validation:
            print("[✗] Patch Validator..................... FAIL (no confidence score)")
            return False

        print("[✓] Patch Validator..................... PASS")
        return True
    except Exception as e:
        print(f"[✗] Patch Validator..................... FAIL ({e})")
        return False


def test_remediation_engine():
    """Test remediation engine."""
    try:
        from modules.patching import RemediationEngine, PatchGenerator

        engine = RemediationEngine()
        generator = PatchGenerator()

        findings = [
            {
                "id": "finding_1",
                "vulnerability_type": "sql_injection",
                "severity": "high",
            },
            {
                "id": "finding_2",
                "vulnerability_type": "xss",
                "severity": "medium",
            },
        ]

        patches = [generator.generate_patch(f) for f in findings]

        plan = engine.create_remediation_plan(findings, patches)

        if "plan_id" not in plan:
            print("[✗] Remediation Engine.................. FAIL (no plan ID)")
            return False

        if "execution_plan" not in plan:
            print("[✗] Remediation Engine.................. FAIL (no execution plan)")
            return False

        if len(plan["execution_plan"]) == 0:
            print("[✗] Remediation Engine.................. FAIL (empty execution plan)")
            return False

        print("[✓] Remediation Engine.................. PASS")
        return True
    except Exception as e:
        print(f"[✗] Remediation Engine.................. FAIL ({e})")
        return False


def test_patch_prioritization():
    """Test patch prioritization."""
    try:
        from modules.patching import PatchGenerator

        generator = PatchGenerator()

        patches = [
            generator.generate_patch({
                "id": f"finding_{i}",
                "vulnerability_type": ["sql_injection", "xss", "rce"][i % 3],
                "severity": ["critical", "high", "medium"][i % 3],
            })
            for i in range(5)
        ]

        # Test prioritization strategies
        for strategy in ["impact", "effort", "roi", "time"]:
            prioritized = generator.prioritize_patches(patches, strategy)
            if len(prioritized) != len(patches):
                print(f"[✗] Patch Prioritization ({strategy}).... FAIL (count mismatch)")
                return False

        print("[✓] Patch Prioritization................ PASS")
        return True
    except Exception as e:
        print(f"[✗] Patch Prioritization................ FAIL ({e})")
        return False


def test_test_suite_generation():
    """Test test suite generation."""
    try:
        from modules.patching import RemediationEngine, PatchGenerator

        engine = RemediationEngine()
        generator = PatchGenerator()

        findings = [
            {"id": "f1", "vulnerability_type": "sql_injection", "severity": "high"},
            {"id": "f2", "vulnerability_type": "xss", "severity": "medium"},
        ]

        patches = [generator.generate_patch(f) for f in findings]
        test_suite = engine.create_test_suite(patches)

        if "tests" not in test_suite:
            print("[✗] Test Suite Generation............... FAIL (no tests)")
            return False

        if len(test_suite["tests"]) != len(patches):
            print("[✗] Test Suite Generation............... FAIL (test count mismatch)")
            return False

        print("[✓] Test Suite Generation............... PASS")
        return True
    except Exception as e:
        print(f"[✗] Test Suite Generation............... FAIL ({e})")
        return False


def test_package_upgrade_path():
    """Test package upgrade path generation."""
    try:
        from modules.patching import PackageAnalyzer

        analyzer = PackageAnalyzer()

        # Test upgrade path for vulnerable Django
        upgrade_path = analyzer.get_upgrade_path("django", "2.2.27")

        if upgrade_path.get("status") != "not_vulnerable" and "steps" not in upgrade_path:
            print("[✗] Package Upgrade Path................ FAIL (no steps)")
            return False

        if "to_version" not in upgrade_path and "status" not in upgrade_path:
            print("[✗] Package Upgrade Path................ FAIL (no version or status)")
            return False

        print("[✓] Package Upgrade Path................ PASS")
        return True
    except Exception as e:
        print(f"[✗] Package Upgrade Path................ FAIL ({e})")
        return False


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("PHASE 5: PATCH ENGINE VERIFICATION")
    print("=" * 70 + "\n")

    tests = [
        ("Patching Module Imports", test_patching_imports),
        ("Patch Generator", test_patch_generator),
        ("Package Analyzer", test_package_analyzer),
        ("Patch Validator", test_patch_validator),
        ("Remediation Engine", test_remediation_engine),
        ("Patch Prioritization", test_patch_prioritization),
        ("Test Suite Generation", test_test_suite_generation),
        ("Package Upgrade Path", test_package_upgrade_path),
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
    print(f"PHASE 5 VERIFICATION: {passed}/{total} checks passed ({percentage:.0f}%)")
    print("=" * 70 + "\n")

    if all(results):
        print("✓ All Phase 5 checks passed!")
        print("✓ Patch engine module is fully functional")
        print("✓ Remediation planning and validation ready\n")
        return 0
    else:
        print("✗ Some checks failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
