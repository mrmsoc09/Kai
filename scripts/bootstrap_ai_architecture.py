#!/usr/bin/env python3
"""Bootstrap Kai AI kernel directories and runtime paths."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ensure_dirs():
    dirs = [
        "runtime/memory/shared",
        "runtime/memory/sessions",
        "runtime/memory/artifacts",
        "runtime/memory/indexes",
        "runtime/logs",
        "runtime/metrics",
        "runtime/traces",
        "runtime/reports",
        "runtime/tmp",
    ]
    for d in dirs:
        (ROOT / d).mkdir(parents=True, exist_ok=True)


def main():
    ensure_dirs()
    print("bootstrap complete")


if __name__ == "__main__":
    main()
