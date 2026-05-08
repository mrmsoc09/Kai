#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

FORBIDDEN_ENV_KEYS = [
    "K1_ENABLE_BOOTSTRAP_AUTH",
    "K1_DEV_TOKEN",
]

DEFAULT_SCAN_FILES = [
    ".env",
    ".env.example",
    ".env.template",
    "docker-compose.yml",
]

ENV_KEY_PATTERN = re.compile(r"^\s*(?:-\s*)?(?P<key>[A-Z0-9_]+)\s*=")


def scan_file(path: Path, forbidden_keys: set[str]) -> list[tuple[int, str, str]]:
    if not path.exists() or not path.is_file():
        return []

    matches: list[tuple[int, str, str]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            env_match = ENV_KEY_PATTERN.match(line)
            if not env_match:
                continue
            key = env_match.group("key")
            if key in forbidden_keys:
                matches.append((lineno, key, line.rstrip("\n")))
    return matches


def scan_environment(forbidden_keys: set[str]) -> list[str]:
    hits: list[str] = []
    for key in forbidden_keys:
        if key in os.environ:
            hits.append(key)
    return hits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that unsafe bootstrap auth environment variables are not present in repo files or running environment.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_SCAN_FILES,
        help="Files and paths to scan for forbidden bootstrap auth variables.",
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="Also scan the current process environment for forbidden bootstrap auth keys.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    forbidden = set(FORBIDDEN_ENV_KEYS)
    total_issues = 0

    for raw_path in args.paths:
        path = Path(raw_path)
        if path.is_dir():
            for child in sorted(path.glob("**/*")):
                if child.is_file():
                    matches = scan_file(child, forbidden)
                    for lineno, key, text in matches:
                        print(f"[FORBIDDEN] {child}:{lineno}: {key} -> {text}")
                        total_issues += 1
        else:
            matches = scan_file(path, forbidden)
            for lineno, key, text in matches:
                print(f"[FORBIDDEN] {path}:{lineno}: {key} -> {text}")
                total_issues += 1

    if args.check_env:
        env_hits = scan_environment(forbidden)
        for key in env_hits:
            print(f"[FORBIDDEN] environment variable set: {key}")
            total_issues += 1

    if total_issues:
        print(f"Validation failed: {total_issues} forbidden bootstrap auth entries found.")
        return 1

    print("Validation passed: no forbidden bootstrap auth entries found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
