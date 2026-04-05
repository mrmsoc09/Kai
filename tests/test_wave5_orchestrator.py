from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from apps.backend.src.core.midnight_orchestrator import (
    MidnightOrchestrator,
)


def test_midnight_orchestrator_importable() -> None:
    assert MidnightOrchestrator is not None


def test_midnight_orchestrator_init() -> None:
    orchestrator = MidnightOrchestrator()
    assert orchestrator.RESERVE_RATIO == 0.15
    assert orchestrator.SPIDERFOOT_TIER_0
    assert orchestrator.SPIDERFOOT_TIER_1


def test_calculate_allocations_three_scans() -> None:
    orchestrator = MidnightOrchestrator()

    quota_data = {
        "SHODAN_API_KEY": {
            "remaining": 100,
            "daily_limit": 100,
        },
        "GITHUB_TOKEN": {
            "remaining": 500,
            "daily_limit": 500,
        },
    }

    scan_queue = [
        {"scan_id": "scan_1"},
        {"scan_id": "scan_2"},
        {"scan_id": "scan_3"},
    ]

    allocations = orchestrator._calculate_allocations(
        quota_data, scan_queue
    )

    assert "SHODAN_API_KEY" in allocations
    assert "GITHUB_TOKEN" in allocations

    shodan_alloc = allocations["SHODAN_API_KEY"]["scan_1"]
    expected = int(100 * (1 - 0.15) // 3)
    assert shodan_alloc == expected


def test_write_default_scripts() -> None:
    with TemporaryDirectory() as tmpdir:
        orchestrator = MidnightOrchestrator()
        orchestrator.OUTPUT_DIR = Path(tmpdir)
        orchestrator._write_default_scripts()

        default_path = Path(tmpdir) / "default_api_keys.sh"
        assert default_path.exists()
        content = default_path.read_text()
        assert "midnight orchestrator fallback" in content


def test_spiderfoot_tiers_valid() -> None:
    orchestrator = MidnightOrchestrator()

    assert isinstance(orchestrator.SPIDERFOOT_TIER_0, list)
    assert len(orchestrator.SPIDERFOOT_TIER_0) > 0

    assert isinstance(orchestrator.SPIDERFOOT_TIER_1, dict)
    assert len(orchestrator.SPIDERFOOT_TIER_1) > 0

    for module, env_var in \
            orchestrator.SPIDERFOOT_TIER_1.items():
        assert isinstance(module, str)
        assert isinstance(env_var, str)


def test_reconcile_after_scan() -> None:
    with TemporaryDirectory() as tmpdir:
        orchestrator = MidnightOrchestrator()
        orchestrator.SIGNAL_HISTORY_PATH = (
            Path(tmpdir) / "signals.json"
        )
        orchestrator.SIGNAL_HISTORY_PATH.parent.mkdir(
            parents=True, exist_ok=True
        )

        orchestrator.reconcile_after_scan(
            scan_id="test_scan_1",
            actual_usage={"SHODAN_API_KEY": 10},
            findings_per_source={"SHODAN_API_KEY": 5},
        )

        assert orchestrator.SIGNAL_HISTORY_PATH.exists()
        history = json.loads(
            orchestrator.SIGNAL_HISTORY_PATH.read_text()
        )
        assert "SHODAN_API_KEY" in history
        assert len(history["SHODAN_API_KEY"]) > 0
        assert history["SHODAN_API_KEY"][0]["scan_id"] == (
            "test_scan_1"
        )


def test_output_dir_created() -> None:
    orchestrator = MidnightOrchestrator()
    assert orchestrator.OUTPUT_DIR.exists()
