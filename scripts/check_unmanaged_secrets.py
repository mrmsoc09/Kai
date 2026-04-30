#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = list(ROOT.glob("apps/backend/src/**/*.py"))

# These modules are the approved boundary for direct env secret reads.
ALLOW_FILES = {
    Path("apps/backend/src/core/secret_manager.py"),
    Path("apps/backend/src/core/hil_vault_client.py"),
    # mailer reads SMTP credentials from env by design: prevents SSRF via
    # caller-injected credentials. See docstring in _send_via_smtp.
    Path("apps/backend/src/routers/mailer.py"),
    # Vault bootstrap: these files MUST read VAULT_TOKEN from env to initialise
    # the Vault client — you cannot use the secret manager before Vault is ready.
    Path("apps/backend/src/main.py"),
    Path("apps/backend/src/core/vault_auth.py"),
    Path("apps/backend/src/core/vault_client.py"),
    # Notification sink: reads Telegram bot token by design (same rationale as mailer).
    Path("apps/backend/src/core/trilium/alerter.py"),
    # Finance read-only mirrors: API keys are injected at construction or from env
    # as a last-resort fallback; caller (Celery task) is responsible for Vault injection.
    Path("apps/backend/src/executive/mirrors/kraken.py"),
    Path("apps/backend/src/executive/mirrors/coinbase.py"),
}

SECRET_ENV_RE = re.compile(
    r"""(?P<call>os\.getenv|os\.environ\.get)\(\s*["'](?P<name>[A-Z0-9_]+)["']""",
)
SENSITIVE_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_PASS")

# Non-secret env names that happen to include sensitive words.
SAFE_NAME_EXCEPTIONS = {
    "K1_REQUIRED_SECRETS",
}


def _is_sensitive(name: str) -> bool:
    if name in SAFE_NAME_EXCEPTIONS:
        return False
    return name.endswith(SENSITIVE_SUFFIXES)


def main() -> int:
    violations: list[str] = []
    for file_path in PYTHON_FILES:
        rel = file_path.relative_to(ROOT)
        if rel in ALLOW_FILES:
            continue

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        for line_no, line in enumerate(lines, start=1):
            for match in SECRET_ENV_RE.finditer(line):
                name = match.group("name")
                if _is_sensitive(name):
                    violations.append(f"{rel}:{line_no} direct_env_secret_read:{name}")

    if violations:
        print("unmanaged secret reads detected:")
        for row in violations:
            print(row)
        return 1

    print("no unmanaged secret reads detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
