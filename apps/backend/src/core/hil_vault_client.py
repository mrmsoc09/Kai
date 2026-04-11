from __future__ import annotations

import os
from typing import Any, Dict, Optional

import hvac


class VaultClient:
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None, mount_point: str = "secret"):
        self.url = (url or os.getenv("VAULT_ADDR", "")).strip()
        self.token = (token or os.getenv("VAULT_TOKEN", "")).strip()
        if not self.url:
            raise RuntimeError("Vault address not configured")
        if not self.token:
            raise RuntimeError("Vault token not configured")
        self.mount_point = mount_point
        self.client = hvac.Client(url=self.url, token=self.token)
        if not self.client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

    def write_secret(self, path: str, data: Dict[str, Any]) -> None:
        self.client.secrets.kv.v2.create_or_update_secret(
            path=path,
            secret=data,
            mount_point=self.mount_point,
        )

    def read_secret(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
            )
            return response.get("data", {}).get("data")
        except hvac.exceptions.InvalidPath:
            return None

    def list_secrets(self, path: str) -> List[str]:
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=self.mount_point,
            )
            return response.get("data", {}).get("keys", [])
        except hvac.exceptions.InvalidPath:
            return []

    def delete_secret(self, path: str) -> None:
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=self.mount_point,
            )
        except hvac.exceptions.InvalidPath:
            pass
