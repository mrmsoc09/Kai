#!/usr/bin/env python3
"""Verify Phase 5 patching endpoints integration."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_endpoint_imports():
    """Test that endpoint modules can be imported."""
    try:
        # Test FastAPI and dependencies
        from fastapi import APIRouter

        # Test routing module
        sys.path.insert(0, str(ROOT / 'apps' / 'backend' / 'src'))
        from routers.findings import (
            router,
            PATCHING_AVAILABLE,
            _get_patching_components,
        )

        print("[✓] Endpoint Module Imports............. PASS")
        return True
    except Exception as e:
        print(f"[✗] Endpoint Module Imports............. FAIL ({e})")
        return False


def test_patching_availability():
    """Test patching module availability."""
    try:
        sys.path.insert(0, str(ROOT / 'apps' / 'backend' / 'src'))
        from routers.findings import PATCHING_AVAILABLE

        if not PATCHING_AVAILABLE:
            print("[✗] Patching Availability............... FAIL (module not available)")
            return False

        print("[✓] Patching Availability............... PASS")
        return True
    except Exception as e:
        print(f"[✗] Patching Availability............... FAIL ({e})")
        return False


def test_component_initialization():
    """Test patching component initialization."""
    try:
        sys.path.insert(0, str(ROOT / 'apps' / 'backend' / 'src'))
        from routers.findings import (
            _get_patching_components,
            PATCHING_AVAILABLE,
        )

        if not PATCHING_AVAILABLE:
            print("[✗] Component Initialization........... FAIL (patching unavailable)")
            return False

        generator, analyzer, validator, engine = _get_patching_components()

        if generator is None or analyzer is None or validator is None or engine is None:
            print("[✗] Component Initialization........... FAIL (components are None)")
            return False

        print("[✓] Component Initialization........... PASS")
        return True
    except Exception as e:
        print(f"[✗] Component Initialization........... FAIL ({e})")
        return False


def test_endpoint_routes():
    """Test that all endpoints are registered."""
    try:
        sys.path.insert(0, str(ROOT / 'apps' / 'backend' / 'src'))
        from routers.findings import router, PATCHING_AVAILABLE

        if not PATCHING_AVAILABLE:
            print("[✗] Endpoint Routes.................... FAIL (patching unavailable)")
            return False

        # Get all routes from router
        routes = [route.path for route in router.routes]

        # Check for key Phase 5 endpoints
        expected_endpoints = [
            '/patching/patches/generate',
            '/patching/patches/generate-batch',
            '/patching/patches/prioritize',
            '/patching/packages/analyze',
            '/patching/packages/analyze-requirements',
            '/patching/validate/patch',
            '/patching/remediation/create-plan',
            '/patching/remediation/execute-phase',
            '/patching/stats',
        ]

        missing = []
        for endpoint in expected_endpoints:
            if not any(endpoint in route for route in routes):
                missing.append(endpoint)

        if missing:
            print(f"[✗] Endpoint Routes.................... FAIL (missing: {missing})")
            return False

        print("[✓] Endpoint Routes.................... PASS")
        return True
    except Exception as e:
        print(f"[✗] Endpoint Routes.................... FAIL ({e})")
        return False


def test_storage_helpers():
    """Test storage helper functions."""
    try:
        sys.path.insert(0, str(ROOT / 'apps' / 'backend' / 'src'))
        from routers.findings import (
            _save_remediation_plan,
            _load_remediation_plan,
            _save_remediation_execution,
            PATCHING_AVAILABLE,
        )

        if not PATCHING_AVAILABLE:
            print("[✗] Storage Helpers.................... FAIL (patching unavailable)")
            return False

        # Test with dummy data
        test_plan = {
            'plan_id': 'test_plan_001',
            'total_findings': 5,
            'status': 'pending',
        }

        _save_remediation_plan('test_plan_001', test_plan)
        loaded = _load_remediation_plan('test_plan_001')

        if not loaded or loaded['plan_id'] != 'test_plan_001':
            print("[✗] Storage Helpers.................... FAIL (save/load mismatch)")
            return False

        print("[✓] Storage Helpers.................... PASS")
        return True
    except Exception as e:
        print(f"[✗] Storage Helpers.................... FAIL ({e})")
        return False


def test_component_methods():
    """Test that all component methods are accessible."""
    try:
        sys.path.insert(0, str(ROOT / 'apps' / 'backend' / 'src'))
        from routers.findings import (
            _get_patching_components,
            PATCHING_AVAILABLE,
        )

        if not PATCHING_AVAILABLE:
            print("[✗] Component Methods.................. FAIL (patching unavailable)")
            return False

        generator, analyzer, validator, engine = _get_patching_components()

        # Check generator methods
        gen_methods = ['generate_patch', 'generate_batch_patches', 'prioritize_patches', 'get_patch_stats']
        for method in gen_methods:
            if not hasattr(generator, method):
                print(f"[✗] Component Methods.................. FAIL (missing PatchGenerator.{method})")
                return False

        # Check analyzer methods
        ana_methods = ['analyze_package', 'analyze_requirements', 'get_upgrade_path', 'check_cve_status']
        for method in ana_methods:
            if not hasattr(analyzer, method):
                print(f"[✗] Component Methods.................. FAIL (missing PackageAnalyzer.{method})")
                return False

        # Check validator methods
        val_methods = ['validate_patch', 'validate_patch_applicability', 'validate_patch_compatibility']
        for method in val_methods:
            if not hasattr(validator, method):
                print(f"[✗] Component Methods.................. FAIL (missing PatchValidator.{method})")
                return False

        # Check engine methods
        eng_methods = ['create_remediation_plan', 'execute_remediation_phase', 'create_test_suite']
        for method in eng_methods:
            if not hasattr(engine, method):
                print(f"[✗] Component Methods.................. FAIL (missing RemediationEngine.{method})")
                return False

        print("[✓] Component Methods.................. PASS")
        return True
    except Exception as e:
        print(f"[✗] Component Methods.................. FAIL ({e})")
        return False


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("PHASE 5 ENDPOINTS VERIFICATION")
    print("=" * 70 + "\n")

    tests = [
        ("Endpoint Module Imports", test_endpoint_imports),
        ("Patching Availability", test_patching_availability),
        ("Component Initialization", test_component_initialization),
        ("Endpoint Routes", test_endpoint_routes),
        ("Storage Helpers", test_storage_helpers),
        ("Component Methods", test_component_methods),
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
    print(f"ENDPOINT VERIFICATION: {passed}/{total} checks passed ({percentage:.0f}%)")
    print("=" * 70 + "\n")

    if all(results):
        print("✓ All endpoint checks passed!")
        print("✓ Phase 5 patching endpoints fully integrated")
        print("✓ Ready for API testing\n")
        return 0
    else:
        print("✗ Some checks failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
