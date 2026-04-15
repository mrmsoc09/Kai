from __future__ import annotations

import os
import logging
from typing import Optional
import hvac

logger = logging.getLogger(__name__)

class VaultCredentialProvider:
    """
    Fetches API keys from HashiCorp Vault.
    Credentials held in volatile memory only.
    """

    def __init__(self):
        self.url = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        self.token = os.getenv("VAULT_TOKEN")

    def get_secret(self, path: str, key: str) -> Optional[str]:
        try:
            client = hvac.Client(url=self.url, token=self.token)
            read_response = client.secrets.kv.v2.read_secret_version(path=path)
            data = read_response.get("data", {}).get("data", {})
            return data.get(key)
        except Exception as e:
            logger.error(f"Failed to fetch secret from Vault at {path}: {e}")
            return None
