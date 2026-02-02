#!/usr/bin/env python3
"""Phase 3: Program Discovery Verification Script."""

import sys
import json
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def test_discovery_imports():
    """Test that discovery module can be imported."""
    try:
        from modules.discovery import ProgramLoader, ProgramScorer, TargetSelector
        print("[✓] Discovery Module Imports............. PASS")
        return True
    except ImportError as e:
        print(f"[✗] Discovery Module Imports............. FAIL ({e})")
        return False


def test_program_loader():
    """Test program loading functionality."""
    try:
        from modules.discovery import ProgramLoader

        loader = ProgramLoader()
        programs = loader.load_programs()

        if not programs:
            print("[✗] Program Loader........................ FAIL (no programs loaded)")
            return False

        if not isinstance(programs, list):
            print("[✗] Program Loader........................ FAIL (programs not a list)")
            return False

        # Check program structure
        first_prog = programs[0]
        required_fields = ["id", "name", "platform", "program_url"]
        if not all(field in first_prog for field in required_fields):
            print("[✗] Program Loader........................ FAIL (missing required fields)")
            return False

        print(f"[✓] Program Loader........................ PASS ({len(programs)} programs)")
        return True
    except Exception as e:
        print(f"[✗] Program Loader........................ FAIL ({e})")
        return False


def test_program_filtering():
    """Test program filtering capabilities."""
    try:
        from modules.discovery import ProgramLoader

        loader = ProgramLoader()
        programs = loader.load_programs()

        # Test filter by market
        cloud_programs = loader.filter_programs(market="cloud")
        if not isinstance(cloud_programs, list):
            print("[✗] Program Filtering..................... FAIL (filter result not a list)")
            return False

        # Test filter by exploitability tag
        web_programs = loader.filter_programs(exploitability_tags=["web"])
        if not isinstance(web_programs, list):
            print("[✗] Program Filtering..................... FAIL (tag filter failed)")
            return False

        print(f"[✓] Program Filtering..................... PASS (found {len(cloud_programs)} cloud, {len(web_programs)} web)")
        return True
    except Exception as e:
        print(f"[✗] Program Filtering..................... FAIL ({e})")
        return False


def test_program_statistics():
    """Test program statistics calculation."""
    try:
        from modules.discovery import ProgramLoader

        loader = ProgramLoader()
        stats = loader.get_program_stats()

        if "total" not in stats or "verified" not in stats:
            print("[✗] Program Statistics.................... FAIL (missing stats fields)")
            return False

        if stats["total"] == 0:
            print("[✗] Program Statistics.................... FAIL (no programs)")
            return False

        print(f"[✓] Program Statistics.................... PASS ({stats['total']} total, {stats['verified']} verified)")
        return True
    except Exception as e:
        print(f"[✗] Program Statistics.................... FAIL ({e})")
        return False


def test_program_scorer():
    """Test program scoring engine."""
    try:
        from modules.discovery import ProgramLoader, ProgramScorer

        loader = ProgramLoader()
        scorer = ProgramScorer()
        programs = loader.load_programs()

        if not programs:
            print("[✗] Program Scorer........................ FAIL (no programs to score)")
            return False

        # Score a single program
        first_prog = programs[0]
        score = scorer.score_program(first_prog)

        if "score" not in score or score["score"] < 0 or score["score"] > 1:
            print("[✗] Program Scorer........................ FAIL (invalid score)")
            return False

        # Score multiple programs
        scores = scorer.score_programs(programs, sort=True)
        if not isinstance(scores, list) or len(scores) == 0:
            print("[✗] Program Scorer........................ FAIL (batch scoring failed)")
            return False

        # Check that scores are sorted
        sorted_scores = [s["score"] for s in scores]
        if sorted_scores != sorted(sorted_scores, reverse=True):
            print("[✗] Program Scorer........................ FAIL (scores not sorted)")
            return False

        print(f"[✓] Program Scorer........................ PASS (scored {len(scores)} programs)")
        return True
    except Exception as e:
        print(f"[✗] Program Scorer........................ FAIL ({e})")
        return False


def test_score_by_objective():
    """Test scoring by different objectives."""
    try:
        from modules.discovery import ProgramLoader, ProgramScorer

        loader = ProgramLoader()
        scorer = ProgramScorer()
        programs = loader.load_programs()

        if not programs:
            print("[✗] Score by Objective..................... FAIL (no programs)")
            return False

        objectives = ["balanced", "high_payout", "high_confidence", "research"]
        results = {}

        for obj in objectives:
            ranked = scorer.rank_for_k1_objective(programs, obj)
            if not isinstance(ranked, list) or len(ranked) == 0:
                print(f"[✗] Score by Objective..................... FAIL ({obj} failed)")
                return False
            results[obj] = len(ranked)

        print(f"[✓] Score by Objective..................... PASS (all objectives working)")
        return True
    except Exception as e:
        print(f"[✗] Score by Objective..................... FAIL ({e})")
        return False


def test_target_selector():
    """Test intelligent target selection."""
    try:
        from modules.discovery import ProgramLoader, ProgramScorer, TargetSelector

        loader = ProgramLoader()
        scorer = ProgramScorer()
        selector = TargetSelector()
        programs = loader.load_programs()

        if not programs:
            print("[✗] Target Selector....................... FAIL (no programs)")
            return False

        scores = scorer.score_programs(programs, sort=True)

        # Test single target selection
        selected = selector.select_target(programs, scores, strategy="greedy")
        if not selected or "program_id" not in selected:
            print("[✗] Target Selector....................... FAIL (single selection failed)")
            return False

        # Test batch selection
        batch = selector.select_batch(programs, scores, batch_size=3, strategy="diverse")
        if not isinstance(batch, list) or len(batch) == 0:
            print("[✗] Target Selector....................... FAIL (batch selection failed)")
            return False

        # Test rotation selection
        rotation = selector.select_for_rotation(programs, scores, rotation_days=7)
        if not isinstance(rotation, list):
            print("[✗] Target Selector....................... FAIL (rotation selection failed)")
            return False

        print(f"[✓] Target Selector....................... PASS (strategies working)")
        return True
    except Exception as e:
        print(f"[✗] Target Selector....................... FAIL ({e})")
        return False


def test_autonomy_tier_recommendations():
    """Test autonomy tier-based recommendations."""
    try:
        from modules.discovery import ProgramLoader, ProgramScorer, TargetSelector

        loader = ProgramLoader()
        scorer = ProgramScorer()
        selector = TargetSelector()
        programs = loader.load_programs()

        if not programs:
            print("[✗] Autonomy Tier Recommendations........ FAIL (no programs)")
            return False

        scores = scorer.score_programs(programs, sort=True)

        # Test each autonomy tier
        for tier in range(4):
            recommended = selector.recommend_for_autonomy_tier(programs, scores, tier)
            if not isinstance(recommended, list):
                print(f"[✗] Autonomy Tier Recommendations........ FAIL (tier {tier} failed)")
                return False

        print(f"[✓] Autonomy Tier Recommendations........ PASS (all tiers working)")
        return True
    except Exception as e:
        print(f"[✗] Autonomy Tier Recommendations........ FAIL ({e})")
        return False


def test_selection_metrics():
    """Test selection metrics tracking."""
    try:
        from modules.discovery import ProgramLoader, ProgramScorer, TargetSelector

        loader = ProgramLoader()
        scorer = ProgramScorer()
        selector = TargetSelector()
        programs = loader.load_programs()
        scores = scorer.score_programs(programs, sort=True)

        # Make some selections
        selector.select_target(programs, scores, strategy="greedy")
        selector.select_batch(programs, scores, batch_size=3)

        # Get metrics
        metrics = selector.get_selection_metrics()

        if "total_selections" not in metrics or metrics["total_selections"] < 2:
            print("[✗] Selection Metrics..................... FAIL (metrics not tracked)")
            return False

        print(f"[✓] Selection Metrics..................... PASS ({metrics['total_selections']} selections tracked)")
        return True
    except Exception as e:
        print(f"[✗] Selection Metrics..................... FAIL ({e})")
        return False


def test_discovery_data_quality():
    """Test quality of loaded discovery data."""
    try:
        from modules.discovery import ProgramLoader

        loader = ProgramLoader()
        programs = loader.load_programs()

        if not programs:
            print("[✗] Discovery Data Quality................ FAIL (no data)")
            return False

        # Check for minimal required data
        verified_count = sum(1 for p in programs if p.get("source_verified"))
        with_payouts = sum(1 for p in programs if p.get("payout_max_usd"))
        with_tags = sum(1 for p in programs if p.get("exploitability_tags"))

        if verified_count == 0:
            print("[✗] Discovery Data Quality................ FAIL (no verified programs)")
            return False

        print(f"[✓] Discovery Data Quality................ PASS ({verified_count} verified, {with_payouts} with payouts)")
        return True
    except Exception as e:
        print(f"[✗] Discovery Data Quality................ FAIL ({e})")
        return False


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("PHASE 3: PROGRAM DISCOVERY VERIFICATION")
    print("=" * 70 + "\n")

    tests = [
        ("Discovery Module Imports", test_discovery_imports),
        ("Program Loader", test_program_loader),
        ("Program Filtering", test_program_filtering),
        ("Program Statistics", test_program_statistics),
        ("Program Scorer", test_program_scorer),
        ("Score by Objective", test_score_by_objective),
        ("Target Selector", test_target_selector),
        ("Autonomy Tier Recommendations", test_autonomy_tier_recommendations),
        ("Selection Metrics", test_selection_metrics),
        ("Discovery Data Quality", test_discovery_data_quality),
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
    print(f"PHASE 3 VERIFICATION: {passed}/{total} checks passed ({percentage:.0f}%)")
    print("=" * 70 + "\n")

    if all(results):
        print("✓ All Phase 3 checks passed!")
        print("✓ Program Discovery module is fully functional")
        print("✓ Intelligent target selection ready for use\n")
        return 0
    else:
        print("✗ Some checks failed. Review output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
