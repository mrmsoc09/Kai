"""Vault integration for opportunity credentials.

Manages storage, retrieval, and deletion of credentials in HashiCorp Vault.
All operations are wrapped in audit logging for compliance and debugging.
"""
from __future__ import annotations

import logging
from typing import Any

from .audit_logger import write_audit_record
from .vault_client import VaultClient, SecretNotFoundError, VaultConnectionError

logger = logging.getLogger(__name__)


class OpportunityCredentialsVault:
    """Secure storage and retrieval of opportunity credentials via Vault."""

    def __init__(self, vault_client: VaultClient | None = None):
        """
        Initialize the Vault credentials manager.

        Args:
            vault_client: Existing VaultClient instance (for testing/injection).
                         If None, a new one is created.
        """
        self.vc = vault_client or VaultClient()

    def _vault_path(self, program_id: str, access_type: str) -> str:
        """Build the Vault secret path for a credential."""
        return f"secret/opportunities/{program_id}/credentials/{access_type}"

    async def store_credentials(
        self,
        program_id: str,
        access_type: str,
        credentials: dict[str, Any],
        user_id: str = "unknown",
    ) -> str:
        """
        Store credentials in Vault.

        Args:
            program_id: Program UUID as string
            access_type: Type of access ("user_account", "api_key", etc.)
            credentials: Dict of credential fields (never logged)
            user_id: ID of user storing the credential

        Returns:
            Vault secret path

        Raises:
            VaultConnectionError: If Vault operation fails
        """
        vault_path = self._vault_path(program_id, access_type)

        try:
            self.vc.write_secret(vault_path, credentials, overwrite=True)
            logger.info(f"Credential stored for {program_id}/{access_type}")

            # Audit log
            write_audit_record(
                "credential.stored",
                user_id=user_id,
                decision="stored",
                reason=f"Stored {access_type} credential",
                detail={"program_id": program_id, "access_type": access_type},
            )

            return vault_path
        except VaultConnectionError as e:
            logger.error(f"Failed to store credential: {str(e)}")
            write_audit_record(
                "credential.store_failed",
                user_id=user_id,
                decision="failed",
                reason=f"Failed to store {access_type} credential",
                detail={
                    "program_id": program_id,
                    "access_type": access_type,
                    "error": str(e),
                },
            )
            raise

    async def read_credentials(
        self,
        program_id: str,
        access_type: str,
        user_id: str = "unknown",
    ) -> dict[str, Any]:
        """
        Read credentials from Vault.

        Args:
            program_id: Program UUID as string
            access_type: Type of access
            user_id: ID of user accessing the credential (for audit)

        Returns:
            Dict of credential fields

        Raises:
            SecretNotFoundError: If credential doesn't exist
            VaultConnectionError: If Vault operation fails
        """
        vault_path = self._vault_path(program_id, access_type)

        try:
            credentials = self.vc.read_secret(vault_path)
            logger.info(f"Credential retrieved for {program_id}/{access_type}")

            # Audit log
            write_audit_record(
                "credential.accessed",
                user_id=user_id,
                decision="accessed",
                reason=f"Retrieved {access_type} credential for scanning",
                detail={"program_id": program_id, "access_type": access_type},
            )

            return credentials
        except SecretNotFoundError:
            logger.warning(f"Credential not found: {vault_path}")
            write_audit_record(
                "credential.access_failed",
                user_id=user_id,
                decision="not_found",
                reason=f"Credential not found for {access_type}",
                detail={"program_id": program_id, "access_type": access_type},
            )
            raise
        except VaultConnectionError as e:
            logger.error(f"Failed to read credential: {str(e)}")
            write_audit_record(
                "credential.access_failed",
                user_id=user_id,
                decision="error",
                reason=f"Failed to access {access_type} credential",
                detail={
                    "program_id": program_id,
                    "access_type": access_type,
                    "error": str(e),
                },
            )
            raise

    async def delete_credentials(
        self,
        program_id: str,
        access_type: str,
        user_id: str = "unknown",
    ) -> None:
        """
        Delete credentials from Vault.

        Args:
            program_id: Program UUID as string
            access_type: Type of access
            user_id: ID of user deleting the credential

        Raises:
            SecretNotFoundError: If credential doesn't exist
            VaultConnectionError: If Vault operation fails
        """
        vault_path = self._vault_path(program_id, access_type)

        try:
            self.vc.delete_secret(vault_path)
            logger.info(f"Credential deleted for {program_id}/{access_type}")

            # Audit log
            write_audit_record(
                "credential.deleted",
                user_id=user_id,
                decision="deleted",
                reason=f"Deleted {access_type} credential",
                detail={"program_id": program_id, "access_type": access_type},
            )
        except SecretNotFoundError:
            logger.warning(f"Attempted to delete non-existent credential: {vault_path}")
            write_audit_record(
                "credential.delete_failed",
                user_id=user_id,
                decision="not_found",
                reason=f"Credential not found for deletion",
                detail={"program_id": program_id, "access_type": access_type},
            )
            raise
        except VaultConnectionError as e:
            logger.error(f"Failed to delete credential: {str(e)}")
            write_audit_record(
                "credential.delete_failed",
                user_id=user_id,
                decision="error",
                reason=f"Failed to delete {access_type} credential",
                detail={
                    "program_id": program_id,
                    "access_type": access_type,
                    "error": str(e),
                },
            )
            raise
