#!/usr/bin/env python3
"""
Render VPN/proxy egress environment variables from Vault network credential entries.

Reads:
  secret/data/kaison/network/<provider_id>

Writes:
  runtime/network/egress.env (default) with mode 0600
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from apps.backend.src.core.vault_client import SecretNotFoundError, VaultClient


PROVIDERS = (
    "protonvpn",
    "mullvadvpn",
    "decodo_residential",
    "decodo_mobile",
)


def _read_provider(vault: VaultClient, provider_id: str) -> dict[str, str]:
    path = f"secret/data/kaison/network/{provider_id}"
    try:
        raw = vault.read_secret(path)
    except SecretNotFoundError:
        return {}
    return {
        key: value.strip()
        for key, value in (raw or {}).items()
        if isinstance(value, str) and value.strip()
    }


def _proxy_url_from_parts(data: dict[str, str], *, default_scheme: str = "http") -> str:
    proxy_url = data.get("proxy_url", "")
    if proxy_url:
        return proxy_url
    endpoint = data.get("endpoint", "")
    if not endpoint:
        return ""
    username = data.get("username", "")
    secret = data.get("password") or data.get("pat") or data.get("api_key") or ""
    if username and secret:
        return f"{default_scheme}://{username}:{secret}@{endpoint}"
    return f"{default_scheme}://{endpoint}"


def build_env(vault: VaultClient) -> dict[str, str]:
    env: dict[str, str] = {}

    for provider_id in PROVIDERS:
        data = _read_provider(vault, provider_id)
        if not data:
            continue
        prefix = f"K1_NETWORK_{provider_id.upper()}"
        for field_name in ("username", "password", "pat", "api_key", "endpoint", "proxy_url"):
            value = data.get(field_name)
            if value:
                env[f"{prefix}_{field_name.upper()}"] = value

        if provider_id == "decodo_residential":
            proxy_url = _proxy_url_from_parts(data)
            if proxy_url:
                env["K1_RESIDENTIAL_PROXY_URL"] = proxy_url
                env["K1_USE_PROXIES"] = "true"
        if provider_id == "decodo_mobile":
            proxy_url = _proxy_url_from_parts(data)
            if proxy_url:
                env["K1_MOBILE_PROXY_URL"] = proxy_url

    return env


def write_env_file(path: Path, env_map: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in sorted(env_map.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.chmod(path, 0o600)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="runtime/network/egress.env",
        help="Output env file path (default: runtime/network/egress.env)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vault = VaultClient()
    env_map = build_env(vault)
    output_path = Path(args.output).resolve()
    write_env_file(output_path, env_map)
    print(f"Wrote {len(env_map)} environment variables to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
