import csv
import io
import logging
import os
import re
from typing import Dict, List, Optional
import hvac
from fastapi import UploadFile, HTTPException
import pypdf
from .secret_manager import EnvSecretProvider, get_secret_manager

logger = logging.getLogger(__name__)

class KeyManager:
    def __init__(self, vault_token: Optional[str] = None):
        self.vault_url = os.getenv("VAULT_URL", "http://k1_vault:8200")
        self.vault_token = self._resolve_vault_token(vault_token)
        self.client = hvac.Client(url=self.vault_url, token=self.vault_token)
        self.mount_point = "secret"

    def _is_non_production(self) -> bool:
        return os.getenv("ENVIRONMENT", "development").strip().lower() != "production"

    def _allow_dev_root_fallback(self) -> bool:
        if not self._is_non_production():
            return False
        if os.getenv("K1_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
            return True
        return os.getenv("K1_ALLOW_DEV_VAULT_ROOT", "").strip().lower() in {"1", "true", "yes", "on"}

    def _resolve_vault_token(self, explicit_token: Optional[str]) -> str:
        if explicit_token and explicit_token.strip():
            return explicit_token.strip()

        env_token = EnvSecretProvider().get_secret("VAULT_TOKEN")
        if env_token:
            return env_token

        secret_token: Optional[str] = None
        try:
            secret_token = get_secret_manager().get_optional("VAULT_TOKEN")
        except Exception as exc:
            logger.warning("Secret manager lookup for VAULT_TOKEN failed: %s", exc)

        if secret_token and secret_token.strip():
            return secret_token.strip()

        if self._allow_dev_root_fallback():
            logger.warning(
                "Using explicit non-production Vault token fallback ('root'). "
                "Set VAULT_TOKEN or disable K1_TEST_MODE/K1_ALLOW_DEV_VAULT_ROOT."
            )
            return "root"

        raise RuntimeError(
            "VAULT_TOKEN is not configured. Provide an explicit token, set VAULT_TOKEN in the environment, "
            "or configure secret-manager retrieval."
        )

    def is_authenticated(self) -> bool:
        return self.client.is_authenticated()

    async def process_key_file(self, file: UploadFile) -> Dict[str, str]:
        """
        Process an uploaded file (CSV or PDF) and extract keys.
        Returns a dictionary of {service: key}.
        """
        filename = file.filename.lower()
        content = await file.read()
        
        extracted_keys = {}

        if filename.endswith(".csv"):
            extracted_keys = self._parse_csv(content)
        elif filename.endswith(".pdf"):
            extracted_keys = self._parse_pdf(content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please use CSV or PDF.")

        if not extracted_keys:
            raise HTTPException(status_code=400, detail="No keys found in the file.")

        # Store in Vault
        self._store_keys_in_vault(extracted_keys)
        
        return {"message": f"Successfully processed and stored {len(extracted_keys)} keys.", "keys_processed": list(extracted_keys.keys())}

    def _parse_csv(self, content: bytes) -> Dict[str, str]:
        keys = {}
        try:
            # Decode bytes to string
            text = content.decode("utf-8")
            reader = csv.reader(io.StringIO(text))
            for row in reader:
                if len(row) >= 2:
                    service = row[0].strip()
                    key = row[1].strip()
                    if service and key:
                        keys[service] = key
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid CSV format: {e}")
        return keys

    def _parse_pdf(self, content: bytes) -> Dict[str, str]:
        keys = {}
        try:
            pdf_file = io.BytesIO(content)
            reader = pypdf.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"

            # Line-based parsing:
            # "Service: Key", "Service = Key", "Service | Key", "Service - Key"
            # Also supports table-like columns with 2+ spaces.
            pattern = re.compile(
                r"^\s*([A-Za-z0-9][A-Za-z0-9 _./-]{1,50})\s*[:=|\-]\s*([A-Za-z0-9][A-Za-z0-9_./:+-]{5,})\s*$"
            )

            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                match = pattern.match(line)
                if match:
                    service = match.group(1).strip()
                    key = match.group(2).strip()
                    if service and key:
                        keys[service] = key
                    continue

                # Table-style: split on 2+ spaces
                cols = re.split(r"\s{2,}", line)
                if len(cols) >= 2:
                    service = cols[0].strip()
                    key = cols[1].strip()
                    if service and key and len(key) > 5:
                        keys[service] = key
                        
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid PDF format: {e}")
        return keys

    def _store_keys_in_vault(self, keys: Dict[str, str]):
        try:
            # We store each key individually under the 'kai/' prefix 
            # so SecretManager.get_secret('SERVICE_NAME') can find it.
            prefix = os.getenv("VAULT_SECRET_PREFIX", "kai").strip("/")
            
            for service, key in keys.items():
                # Normalize service name to uppercase with underscores, e.g. SHODAN_API_KEY
                secret_name = service.strip().upper().replace(" ", "_")
                if not secret_name.endswith("_API_KEY") and not secret_name.endswith("_TOKEN"):
                    secret_name = f"{secret_name}_API_KEY"
                
                path = f"{prefix}/{secret_name}"
                
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret={"value": key},
                    mount_point=self.mount_point
                )
                logger.debug(f"Stored {secret_name} in Vault at {path}")
                
            logger.info(f"Successfully stored {len(keys)} keys in Vault individually.")
            
        except Exception as e:
            logger.error(f"Vault storage error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to store keys in Vault: {e}")

# Global instance
key_manager = KeyManager()
