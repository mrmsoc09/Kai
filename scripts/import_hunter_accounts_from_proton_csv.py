#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.backend.src.core.hunter_account_inventory import (
    HunterAccountEnvOverride,
    hunter_accounts_index_path,
    extract_hunter_account_env_overrides,
    inventory_from_csv_rows,
    write_hunter_account_index,
)
from apps.backend.src.core.vault_client import VaultClient


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Proton Pass hunter accounts into Vault.")
    parser.add_argument(
        "--csv",
        default=os.getenv("KAI_HUNTER_ACCOUNTS_CSV", ""),
        help="Path to the Proton Pass CSV export.",
    )
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Update .env with the CSV path, inventory path, and mapped runtime secrets.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Environment file to update when --write-env is enabled.",
    )
    parser.add_argument(
        "--vault-addr",
        default=os.getenv("VAULT_ADDR", "http://127.0.0.1:8200"),
        help="Vault address.",
    )
    parser.add_argument(
        "--vault-token",
        default=os.getenv("VAULT_TOKEN", ""),
        help="Vault token.",
    )
    return parser.parse_args()


def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in list(reader)]


def _quote_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _safe_env_update(env_file: Path, entries: dict[str, str]) -> None:
    existing = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    lines = existing.splitlines()
    rendered: list[str] = []
    seen: set[str] = set()

    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            rendered.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in entries:
            if key not in seen:
                rendered.append(f"{key}={_quote_env_value(entries[key])}")
                seen.add(key)
            continue
        rendered.append(line)

    for key, value in entries.items():
        if key not in seen:
            rendered.append(f"{key}={_quote_env_value(value)}")

    env_file.write_text("\n".join(rendered).rstrip("\n") + "\n", encoding="utf-8")


def _write_vault_env_overrides(vault: Any, overrides: list[HunterAccountEnvOverride]) -> None:
    for override in overrides:
        vault.write_secret(
            f"k1/{override.key}",
            {
                "value": override.value,
                "source_name": override.source_name,
                "source_url": override.source_url or "",
                "source_index": str(override.source_index),
                "source_system": "proton_pass_export",
            },
            overwrite=True,
        )


class _VaultHttpWriter:
    def __init__(self, vault_addr: str, vault_token: str) -> None:
        self.vault_addr = vault_addr.rstrip("/")
        self.vault_token = vault_token

    def write_secret(self, secret_path: str, secret_data: dict[str, Any], overwrite: bool = True) -> None:
        del overwrite
        url = f"{self.vault_addr}/v1/secret/data/{secret_path.lstrip('/')}"
        body = json.dumps({"data": secret_data}).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "X-Vault-Token": self.vault_token,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                if response.status not in {200, 204}:
                    raise RuntimeError(f"Vault write failed with HTTP {response.status}")
        except HTTPError as exc:
            raise RuntimeError(f"Vault write failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Vault write failed: {exc.reason}") from exc


def _build_vault_writer(vault_addr: str, vault_token: str) -> Any:
    vault = VaultClient(vault_addr=vault_addr, vault_token=vault_token)
    if getattr(vault, "client", None) is not None:
        return vault
    return _VaultHttpWriter(vault_addr=vault_addr, vault_token=vault_token)


def _store_records(vault: VaultClient, records: list[Any], rows: list[dict[str, str]]) -> None:
    for record in records:
        row = rows[record.source_index - 1]
        secret_data = {
            "type": row.get("type", ""),
            "name": row.get("name", ""),
            "url": row.get("url", ""),
            "email": row.get("email", ""),
            "username": row.get("username", ""),
            "password": row.get("password", ""),
            "note": row.get("note", ""),
            "totp": row.get("totp", ""),
            "createTime": row.get("createTime", ""),
            "modifyTime": row.get("modifyTime", ""),
            "vault": row.get("vault", ""),
            "platform_hint": record.platform_hint or "",
            "credential_kind": record.credential_kind,
        }
        vault.write_secret(record.vault_path, secret_data, overwrite=True)


def main() -> int:
    args = _parse_args()
    if not args.csv:
        raise SystemExit("Missing --csv or KAI_HUNTER_ACCOUNTS_CSV")

    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    rows = _load_rows(csv_path)
    records, summary = inventory_from_csv_rows(rows, source_path=str(csv_path))
    env_overrides = extract_hunter_account_env_overrides(rows)

    if not args.vault_token:
        raise SystemExit("VAULT_TOKEN is required to import hunter accounts into Vault.")

    vault = _build_vault_writer(args.vault_addr, args.vault_token)
    _store_records(vault, records, rows)
    _write_vault_env_overrides(vault, env_overrides)
    write_hunter_account_index(summary, client=vault)

    if args.write_env:
        _safe_env_update(
            Path(args.env_file),
            {
                "VAULT_ADDR": args.vault_addr,
                "VAULT_TOKEN": args.vault_token,
                "KAI_HUNTER_ACCOUNTS_CSV": str(csv_path),
                "KAI_HUNTER_ACCOUNTS_INDEX_FILE": str(hunter_accounts_index_path()),
                **{override.key: override.value for override in env_overrides},
            },
        )

    print(
        f"Imported {summary['record_count']} hunter/account records into Vault and wrote the summary index."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
