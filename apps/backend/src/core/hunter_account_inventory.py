from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .vault_client import SecretNotFoundError, VaultClient, VaultConnectionError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HunterAccountRecord:
    source_index: int
    slug: str
    display_name: str
    platform_hint: str | None
    credential_kind: str
    username: str | None
    email: str | None
    source_url: str | None
    vault_path: str
    has_password: bool
    has_totp: bool
    has_backup_codes: bool


@dataclass(slots=True)
class HunterAccountEnvOverride:
    key: str
    value: str
    source_index: int
    source_name: str
    source_url: str | None


def _env_path(name: str, default: str) -> Path:
    raw = (os.getenv(name) or "").strip()
    return Path(raw) if raw else Path(default)


def hunter_accounts_index_path() -> Path:
    return _env_path(
        "KAI_HUNTER_ACCOUNTS_INDEX_FILE",
        "/srv/kai/artifacts/hunter-accounts/index.json",
    )


def hunter_accounts_vault_index_path() -> str:
    return (os.getenv("KAI_HUNTER_ACCOUNTS_VAULT_INDEX_PATH") or "k1/hunter-accounts/index").strip()


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "account"


def _host_hint(source_url: str | None, name: str | None, note: str | None) -> str | None:
    for raw in (source_url, name, note):
        text = str(raw or "").strip().lower()
        if not text:
            continue
        if "hackerone" in text:
            return "hackerone"
        if "bugcrowd" in text:
            return "bugcrowd"
        if "intigriti" in text:
            return "intigriti"
        if "github" in text:
            return "github"
        if "gitlab" in text:
            return "gitlab"
        if "priceline" in text:
            return "priceline"
        if "twilio" in text or "twillio" in text:
            return "twilio"
    if source_url:
        parsed = urlparse(source_url)
        host = (parsed.netloc or parsed.path or "").lower().split("@")[-1]
        if host:
            return host.split(":")[0].split(".")[0]
    return None


def _credential_kind(name: str, url: str | None, note: str | None, password: str | None, totp: str | None) -> str:
    text = " ".join([name or "", url or "", note or ""]).lower()
    if any(term in text for term in ("api key", "apikey", "api-key", "token", "bearer")):
        return "api_key"
    if any(term in text for term in ("hackerone", "bugcrowd", "intigriti", "researcher", "hunter", "bug bounty")):
        return "hunter_account"
    if password or totp:
        return "user_account"
    return "user_account"


def _backup_codes_present(note: str | None) -> bool:
    text = (note or "").lower()
    return any(term in text for term in ("backup code", "recovery code", "recovery codes", "backup codes"))


def _row_timestamp(row: dict[str, str]) -> int:
    raw = (row.get("createTime") or row.get("modifyTime") or "").strip()
    try:
        return int(raw)
    except ValueError:
        return 0


def _pick_latest_row(rows: list[dict[str, str]], predicate) -> tuple[int, dict[str, str]] | None:
    selected: tuple[int, dict[str, str]] | None = None
    selected_timestamp = -1
    for idx, row in enumerate(rows, start=1):
        if not predicate(row):
            continue
        timestamp = _row_timestamp(row)
        if selected is None or timestamp > selected_timestamp or (
            timestamp == selected_timestamp and idx > selected[0]
        ):
            selected = (idx, row)
            selected_timestamp = timestamp
    return selected


def _first_regex_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            if match.groups():
                group = next((item for item in match.groups() if item), None)
                if group:
                    return group.strip()
            return match.group(0).strip()
    return None


def _row_blob(row: dict[str, str]) -> str:
    return " ".join(
        str(row.get(field) or "")
        for field in ("type", "name", "url", "email", "username", "password", "note")
    ).lower()


def _row_value(row: dict[str, str], *fields: str) -> str | None:
    for field in fields:
        value = (row.get(field) or "").strip()
        if value:
            return value
    return None


def _make_override(
    key: str,
    value: str | None,
    *,
    source_index: int,
    row: dict[str, str],
) -> HunterAccountEnvOverride | None:
    if not value:
        return None
    return HunterAccountEnvOverride(
        key=key,
        value=value.strip(),
        source_index=source_index,
        source_name=(row.get("name") or "").strip() or key,
        source_url=((row.get("url") or "").strip() or None),
    )


def extract_hunter_account_env_overrides(rows: list[dict[str, str]]) -> list[HunterAccountEnvOverride]:
    """Extract the runtime-facing env vars that should mirror the CSV export."""
    overrides: list[HunterAccountEnvOverride] = []

    def add(key: str, value: str | None, source_index: int, row: dict[str, str]) -> None:
        override = _make_override(key, value, source_index=source_index, row=row)
        if override is not None:
            overrides.append(override)

    def latest_match(predicate):
        return _pick_latest_row(rows, predicate)

    # OpenRouter
    match = latest_match(lambda row: "openrouter" in _row_blob(row))
    if match:
        idx, row = match
        text = " ".join(filter(None, [row.get("note") or "", row.get("password") or ""]))
        add("OPENROUTER_API_KEY", _first_regex_match(text, [r"(sk-or-v1-[A-Za-z0-9_-]+)"]), idx, row)

    # OpenAI
    match = latest_match(lambda row: "openai" in _row_blob(row) or "chatgpt" in _row_blob(row))
    if match:
        idx, row = match
        text = " ".join(filter(None, [row.get("note") or "", row.get("password") or ""]))
        add("OPENAI_API_KEY", _first_regex_match(text, [r"(sk-proj-[A-Za-z0-9_-]+)"]), idx, row)

    # HackerOne
    match = latest_match(lambda row: "hackerone" in _row_blob(row) or "hacker one" in _row_blob(row))
    if match:
        idx, row = match
        note_text = row.get("note") or ""
        add("HACKERONE_API_KEY", _first_regex_match(note_text, [r"([A-Za-z0-9+/=]{20,})"]), idx, row)
        add("HACKERONE_USERNAME", _row_value(row, "username", "email"), idx, row)
        add("HACKERONE_USER_ACCOUNT_PASSWORD", _row_value(row, "password"), idx, row)

    # Intigriti
    match = latest_match(lambda row: "intigriti" in _row_blob(row))
    if match:
        idx, row = match
        note_text = row.get("note") or ""
        add("INTIGRITI_API_KEY", _first_regex_match(note_text, [r"Intigrity_API-Key=([^\s/]+)", r"API-Key=([^\s/]+)"]), idx, row)
        add("INTIGRITI_USERNAME", _row_value(row, "username", "email"), idx, row)
        add("INTIGRITI_USER_ACCOUNT_PASSWORD", _row_value(row, "password"), idx, row)

    # Shodan
    match = latest_match(lambda row: "shodan" in _row_blob(row))
    if match:
        idx, row = match
        add("SHODAN_API_KEY", _row_value(row, "note", "password"), idx, row)

    # Hunter services
    match = latest_match(lambda row: "hunter.io" in _row_blob(row))
    if match:
        idx, row = match
        add("HUNTER_IO_API_KEY", _row_value(row, "note", "password"), idx, row)

    match = latest_match(lambda row: "hunter.how" in _row_blob(row))
    if match:
        idx, row = match
        add("HUNTER_HOW_API_KEY", _row_value(row, "note", "password"), idx, row)

    # GitHub
    match = latest_match(lambda row: "github" in _row_blob(row) and bool(_row_value(row, "note", "password", "username")))
    if match:
        idx, row = match
        note_text = row.get("note") or ""
        add("GITHUB_PAT", _first_regex_match(note_text, [r"(github_pat_[A-Za-z0-9_]+)", r"(ghp_[A-Za-z0-9_]+)"]), idx, row)
        add("GITHUB_TOKEN", _first_regex_match(note_text, [r"(github_pat_[A-Za-z0-9_]+)", r"(ghp_[A-Za-z0-9_]+)"]), idx, row)
        add("GITHUB_USERNAME", _row_value(row, "username", "email"), idx, row)

    # Google
    match = latest_match(lambda row: "google" in _row_blob(row) or "gemini" in _row_blob(row))
    if match:
        idx, row = match
        note_text = row.get("note") or ""
        google_keys = re.findall(r"(AIza[0-9A-Za-z_-]+)", note_text)
        if google_keys:
            add("GOOGLE_API_KEY", google_keys[0], idx, row)
            add("GOOGLE_DEVELOPER_API_KEY", google_keys[0], idx, row)
            add("GOOGLE_CSE_API_KEY", google_keys[0], idx, row)
            if len(google_keys) > 1:
                add("GOOGLE_WORKSPACE_API_KEY", google_keys[1], idx, row)

    # Twilio
    match = latest_match(lambda row: "twilio" in _row_blob(row))
    if match:
        idx, row = match
        add("TWILIO_API_KEY", _row_value(row, "note", "password"), idx, row)

    # Proton
    match = latest_match(lambda row: "account.proton.me" in _row_blob(row) or "proton mail" in _row_blob(row))
    if match:
        idx, row = match
        add("PROTON_ME_EMAIL", _row_value(row, "email", "username"), idx, row)
        add("PROTON_ME_PASSWORD", _row_value(row, "password"), idx, row)

    return overrides


def inventory_from_csv_rows(rows: list[dict[str, str]], *, source_path: str) -> tuple[list[HunterAccountRecord], dict[str, Any]]:
    records: list[HunterAccountRecord] = []
    counts: dict[str, int] = {}

    for idx, row in enumerate(rows, start=1):
        row_type = (row.get("type") or "").strip().lower()
        name = (row.get("name") or "").strip()
        url = (row.get("url") or "").strip() or None
        email = (row.get("email") or "").strip() or None
        username = (row.get("username") or "").strip() or None
        password = (row.get("password") or "").strip() or None
        note = (row.get("note") or "").strip() or None
        totp = (row.get("totp") or "").strip() or None

        if row_type and row_type not in {"login", "note", "alias"} and not (password or totp):
            continue
        if not (name or username or email or url or password or totp or note):
            continue

        display_name = name or username or email or f"account-{idx}"
        credential_kind = _credential_kind(display_name, url, note, password, totp)
        platform_hint = _host_hint(url, display_name, note)
        slug_source = username or email or display_name or f"account-{idx}"
        slug = _slugify(f"{slug_source}-{idx}")
        vault_path = f"k1/hunter-accounts/accounts/{credential_kind}/{slug}"

        records.append(
            HunterAccountRecord(
                source_index=idx,
                slug=slug,
                display_name=display_name,
                platform_hint=platform_hint,
                credential_kind=credential_kind,
                username=username,
                email=email,
                source_url=url,
                vault_path=vault_path,
                has_password=bool(password),
                has_totp=bool(totp),
                has_backup_codes=_backup_codes_present(note),
            )
        )
        counts[credential_kind] = counts.get(credential_kind, 0) + 1

    summary = {
        "source_path": source_path,
        "record_count": len(records),
        "counts": counts,
        "records": [asdict(record) for record in records],
    }
    return records, summary


def load_hunter_account_index(*, client: Any | None = None) -> dict[str, Any]:
    vault = client or VaultClient()
    try:
        raw = vault.read_secret(hunter_accounts_vault_index_path())
        payload = raw.get("summary_json") or raw.get("records_json")
        if isinstance(payload, str) and payload.strip():
            return json.loads(payload)
    except SecretNotFoundError:
        logger.info("Hunter account index not yet imported into Vault.")
    except VaultConnectionError as exc:
        logger.warning("Hunter account index unavailable: %s", exc)
    except json.JSONDecodeError as exc:
        logger.warning("Hunter account index JSON is invalid: %s", exc)
    return {"source_path": "", "record_count": 0, "counts": {}, "records": []}


def write_hunter_account_index(summary: dict[str, Any], *, client: Any | None = None) -> None:
    vault = client or VaultClient()
    vault.write_secret(
        hunter_accounts_vault_index_path(),
        {
            "summary_json": json.dumps(summary, ensure_ascii=False),
        },
        overwrite=True,
    )
