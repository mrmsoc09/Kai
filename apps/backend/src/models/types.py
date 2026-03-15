from __future__ import annotations

import base64
import json
import os
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text, TypeDecorator


class EncryptedText(TypeDecorator):
    """SQLAlchemy type for column-level AES-256-GCM encryption.
    Automatically handles JSON serialization for dict/list values.
    """

    impl = Text
    cache_ok = False

    _encryption_key: Optional[bytes] = None

    @classmethod
    def set_key(cls, key_base64: str) -> None:
        """Set the master encryption key from a base64 string."""
        cls._encryption_key = base64.b64decode(key_base64)
        if len(cls._encryption_key) != 32:
            raise ValueError("AES-256 key must be 32 bytes (decoded)")

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        
        # Serialize to JSON if it's a collection
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)
            
        if not self._encryption_key:
            return value_str

        aesgcm = AESGCM(self._encryption_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, value_str.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")

    def process_result_value(self, value: Optional[str], dialect: Any) -> Any:
        if value is None:
            return None
        if not self._encryption_key:
            # Attempt to parse as JSON anyway
            try:
                return json.loads(value)
            except Exception:
                return value

        try:
            data = base64.b64decode(value)
            nonce = data[:12]
            ciphertext = data[12:]
            aesgcm = AESGCM(self._encryption_key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
            
            try:
                return json.loads(decrypted)
            except Exception:
                return decrypted
        except Exception:
            return value
