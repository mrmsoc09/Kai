import os
from typing import Any, Dict, Optional
import hvac

class VaultClient:
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None, mount_point: str = "secret"):
        self.url = url or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.token = token or os.getenv("VAULT_TOKEN", "root")
        self.mount_point = mount_point
        self.client = hvac.Client(url=self.url, token=self.token)
        if not self.client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

    def write_secret(self, path: str, data: Dict[str, Any]) -> None:
        # KV v2 write: /v1/{mount}/data/{path}
        self.client.secrets.kv.v2.create_or_update_secret(
            path=path, secret=data, mount_point=self.mount_point
        )

    def read_secret(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            res = self.client.secrets.kv.v2.read_secret_version(path=path, mount_point=self.mount_point)
            return res.get("data", {}).get("data")
        except hvac.exceptions.InvalidPath:
            return None
