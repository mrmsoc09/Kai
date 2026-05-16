#!/usr/bin/env python3
"""
Pre-commit hook: block commits that introduce hardcoded credentials.

Checks staged files for:
  1. High-entropy strings that look like passwords/tokens/API keys.
  2. Known dangerous patterns (literal docker-compose env assignments with
     plaintext values, common credential patterns).

Install as a git hook:
    cp scripts/pre-commit-check-secrets.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Or use via pre-commit framework (.pre-commit-config.yaml already configured).
Run manually against all staged files:
    python scripts/pre-commit-check-secrets.py
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path


# ── Constants ────────────────────────────────────────────────────────────────

# Min Shannon entropy to flag a string as high-entropy (tuned to avoid false
# positives on long test identifiers while catching real secrets).
MIN_ENTROPY = 4.0
MIN_SECRET_LENGTH = 20

# Files that are explicitly allowed to contain example/placeholder values.
SAFE_PATHS = frozenset(
    [
        ".env.example",
        ".env.mvp.example",
        ".secrets.baseline",
        ".trufflehog-exclude.txt",
        "docs/secrets-management.md",
    ]
)

# Patterns that flag a line as a hardcoded credential.
# Each tuple is (description, compiled_regex).
CREDENTIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "plaintext docker-compose env assignment",
        re.compile(
            r"(?m)^\s*-\s*(PASSWORD|SECRET|TOKEN|API_KEY|_PASS)\s*=[^$#\n][^{]",
        ),
    ),
    (
        "AWS access key",
        re.compile(r"AKIA[0-9A-Z]{16}"),
    ),
    (
        "generic private key header",
        re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY-----"),
    ),
    (
        "GitHub PAT (classic)",
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    ),
    (
        "GitHub PAT (fine-grained)",
        re.compile(r"github_pat_[a-zA-Z0-9_]{82}"),
    ),
    (
        "Anthropic API key",
        re.compile(r"sk-ant-api[0-9A-Za-z\-]{40,}"),
    ),
    (
        "OpenAI API key",
        re.compile(r"sk-[a-zA-Z0-9]{48}"),
    ),
]

# Extensions skipped entirely (binaries, lock files, compiled assets).
SKIP_EXTENSIONS = frozenset(
    [
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".lock",
        ".pyc",
        ".whl",
        ".egg",
        ".bin",
    ]
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    total = len(s)
    return -sum((c / total) * math.log2(c / total) for c in freq.values())


def _staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
    )
    return [Path(p) for p in result.stdout.splitlines() if p]


def _file_content(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return None


# ── Core checks ──────────────────────────────────────────────────────────────

def check_file(path: Path) -> list[str]:
    violations: list[str] = []

    if path.suffix.lower() in SKIP_EXTENSIONS:
        return violations
    if str(path) in SAFE_PATHS or path.name in SAFE_PATHS:
        return violations

    content = _file_content(path)
    if content is None:
        return violations

    # Pattern-based checks.
    for description, pattern in CREDENTIAL_PATTERNS:
        for match in pattern.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            violations.append(f"{path}:{line_no}: {description}")

    # High-entropy string check on lines that look like assignments.
    assignment_re = re.compile(r"""(?:password|secret|token|api[_-]?key|passwd)\s*[=:]\s*["']?([^"'\s#]{%d,})["']?""" % MIN_SECRET_LENGTH, re.IGNORECASE)
    for line_no, line in enumerate(content.splitlines(), start=1):
        for match in assignment_re.finditer(line):
            candidate = match.group(1)
            # Skip obvious placeholders.
            if re.match(r"^(replace-with-|your_|<|{|\$)", candidate, re.IGNORECASE):
                continue
            if _shannon_entropy(candidate) >= MIN_ENTROPY:
                violations.append(
                    f"{path}:{line_no}: high-entropy value in credential assignment "
                    f"(entropy={_shannon_entropy(candidate):.2f})"
                )

    return violations


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> int:
    staged = _staged_files()
    if not staged:
        return 0

    all_violations: list[str] = []
    for path in staged:
        all_violations.extend(check_file(path))

    if all_violations:
        print("pre-commit: potential secrets detected — commit blocked\n")
        for v in all_violations:
            print(f"  {v}")
        print(
            "\nIf this is a false positive, add the file to SAFE_PATHS "
            "or update .secrets.baseline with: detect-secrets scan > .secrets.baseline"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
