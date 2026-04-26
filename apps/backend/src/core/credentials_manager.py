"""High-level credential management service.

Manages CRUD operations, validation, and scanning mode detection
for opportunity credentials.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import aiohttp
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Program
from ..models.opportunity_credentials import (
    OpportunityAccessMetadata,
    OpportunityCredential,
)
from .opportunity_credentials_vault import OpportunityCredentialsVault
from .vault_client import SecretNotFoundError, VaultConnectionError

logger = logging.getLogger(__name__)


class CredentialsManager:
    """High-level credential management service.

    Handles storing, retrieving, validating, and listing credentials
    for bug bounty opportunities. Integrates with Vault for secret storage
    and database for metadata tracking.
    """

    def __init__(
        self,
        db: AsyncSession,
        vault: OpportunityCredentialsVault | None = None,
    ):
        """
        Initialize the credentials manager.

        Args:
            db: AsyncSession for database operations
            vault: OpportunityCredentialsVault instance (or None to create default)
        """
        self.db = db
        self.vault = vault or OpportunityCredentialsVault()

    async def store_credential(
        self,
        program_id: UUID,
        access_type: str,
        credentials: dict[str, Any],
        username: str | None = None,
        notes: str | None = None,
        user_id: str = "unknown",
    ) -> OpportunityCredential:
        """
        Store a credential in Vault and create/update DB record.

        Args:
            program_id: Program UUID
            access_type: Type of access ("user_account", "api_key", etc.)
            credentials: Dict of credential fields (username, password, api_key, etc.)
            username: Plaintext username/email for display (NOT the password)
            notes: Optional analyst notes
            user_id: ID of user storing the credential

        Returns:
            OpportunityCredential database record

        Raises:
            VaultConnectionError: If Vault storage fails
        """
        # Store in Vault
        vault_path = await self.vault.store_credentials(
            str(program_id), access_type, credentials, user_id
        )

        # Upsert in database
        stmt = select(OpportunityCredential).where(
            (OpportunityCredential.program_id == program_id)
            & (OpportunityCredential.access_type == access_type)
        )
        result = await self.db.execute(stmt)
        existing = result.scalars().first()

        if existing:
            existing.vault_secret_path = vault_path
            existing.credential_username = username
            existing.notes = notes
            existing.status = "active"
            existing.validation_method = "manual"
            existing.last_accessed_at = None
            existing.access_count = 0
            db_record = existing
        else:
            db_record = OpportunityCredential(
                program_id=program_id,
                access_type=access_type,
                vault_secret_path=vault_path,
                credential_username=username,
                notes=notes,
                status="active",
                validation_method="manual",
                created_by=user_id,
            )
            self.db.add(db_record)

        await self.db.flush()
        await self.db.commit()
        return db_record

    async def get_credential(
        self,
        program_id: UUID,
        access_type: str,
        user_id: str = "unknown",
    ) -> dict[str, Any] | None:
        """
        Retrieve credential from Vault (with access tracking).

        Args:
            program_id: Program UUID
            access_type: Type of access
            user_id: ID of user accessing the credential (for audit)

        Returns:
            Dict of credential fields, or None if not found

        Raises:
            VaultConnectionError: If Vault retrieval fails
        """
        # Load DB record to check status
        stmt = select(OpportunityCredential).where(
            (OpportunityCredential.program_id == program_id)
            & (OpportunityCredential.access_type == access_type)
        )
        result = await self.db.execute(stmt)
        cred_record = result.scalars().first()

        if not cred_record:
            return None

        # Retrieve from Vault
        try:
            credentials = await self.vault.read_credentials(
                str(program_id), access_type, user_id
            )
        except SecretNotFoundError:
            logger.warning(f"Credential not found in Vault: {cred_record.vault_secret_path}")
            return None

        # Update access tracking
        cred_record.last_accessed_at = datetime.now(timezone.utc)
        cred_record.last_accessed_by = user_id
        cred_record.access_count = (cred_record.access_count or 0) + 1
        await self.db.commit()

        return credentials

    async def delete_credential(
        self,
        program_id: UUID,
        access_type: str,
        user_id: str = "unknown",
    ) -> None:
        """
        Delete credential from Vault and remove DB record.

        Args:
            program_id: Program UUID
            access_type: Type of access
            user_id: ID of user deleting the credential

        Raises:
            SecretNotFoundError: If credential not found in Vault
            VaultConnectionError: If Vault deletion fails
        """
        # Delete from Vault
        await self.vault.delete_credentials(str(program_id), access_type, user_id)

        # Delete from database
        stmt = delete(OpportunityCredential).where(
            (OpportunityCredential.program_id == program_id)
            & (OpportunityCredential.access_type == access_type)
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def validate_credential(
        self,
        program_id: UUID,
        access_type: str,
        program: Program | None = None,
    ) -> dict[str, Any]:
        """
        Test credential against live service.

        Args:
            program_id: Program UUID
            access_type: Type of access ("user_account" or "api_key")
            program: Program record (loaded if not provided)

        Returns:
            Dict with keys:
                - valid (bool)
                - reason (str)
                - tested_at (str, ISO format) if valid=True
        """
        # Load credential record
        stmt = select(OpportunityCredential).where(
            (OpportunityCredential.program_id == program_id)
            & (OpportunityCredential.access_type == access_type)
        )
        result = await self.db.execute(stmt)
        cred_record = result.scalars().first()

        if not cred_record:
            return {"valid": False, "reason": "Credential not found in database"}

        # Get credentials from Vault
        try:
            credentials = await self.vault.read_credentials(
                str(program_id), access_type, "validator"
            )
        except (SecretNotFoundError, VaultConnectionError) as e:
            return {"valid": False, "reason": f"Cannot retrieve credential from Vault: {str(e)}"}

        # Load program if not provided
        if not program:
            prog_stmt = select(Program).where(Program.id == program_id)
            prog_result = await self.db.execute(prog_stmt)
            program = prog_result.scalars().first()

        if not program:
            return {"valid": False, "reason": "Program not found"}

        # Get base URL from program config
        base_url = program.config_json.get("opportunity", {}).get("program_url")
        if not base_url:
            return {"valid": False, "reason": "Program does not have a base URL configured"}

        # Validate based on access_type
        try:
            if access_type == "user_account":
                result = await self._validate_user_account(base_url, credentials)
            elif access_type == "api_key":
                result = await self._validate_api_key(base_url, credentials)
            else:
                result = {
                    "valid": False,
                    "reason": f"Validation not supported for {access_type}",
                }
        except Exception as e:
            logger.error(f"Validation error for {program_id}/{access_type}: {str(e)}")
            result = {"valid": False, "reason": f"Validation error: {str(e)}"}

        # Update DB record
        cred_record.status = "active" if result["valid"] else "invalid"
        cred_record.validation_method = (
            "login_test" if access_type == "user_account" else "api_ping"
        )
        cred_record.last_validated = datetime.now(timezone.utc)
        await self.db.commit()

        return result

    async def _validate_user_account(
        self, base_url: str, credentials: dict[str, Any]
    ) -> dict[str, Any]:
        """Try to login with user account credentials."""
        if "username" not in credentials or "password" not in credentials:
            return {"valid": False, "reason": "Missing username or password"}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{base_url}/api/auth/login",
                    json={"username": credentials["username"], "password": credentials["password"]},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return {"valid": True, "tested_at": datetime.now(timezone.utc).isoformat()}
                    else:
                        return {"valid": False, "reason": f"Login returned HTTP {resp.status}"}
            except asyncio.TimeoutError:
                return {"valid": False, "reason": "Login request timed out (10s)"}
            except aiohttp.ClientError as e:
                return {"valid": False, "reason": f"Login connection error: {str(e)}"}
            except Exception as e:
                return {"valid": False, "reason": f"Login validation error: {str(e)}"}

    async def _validate_api_key(
        self, base_url: str, credentials: dict[str, Any]
    ) -> dict[str, Any]:
        """Try API health check with API key."""
        if "api_key" not in credentials:
            return {"valid": False, "reason": "Missing api_key"}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{base_url}/api/health",
                    headers={"Authorization": f"Bearer {credentials['api_key']}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    # 200 = success, 401 = auth works but access denied (still valid)
                    if resp.status in [200, 401]:
                        return {"valid": True, "tested_at": datetime.now(timezone.utc).isoformat()}
                    else:
                        return {"valid": False, "reason": f"API returned HTTP {resp.status}"}
            except asyncio.TimeoutError:
                return {"valid": False, "reason": "API request timed out (10s)"}
            except aiohttp.ClientError as e:
                return {"valid": False, "reason": f"API connection error: {str(e)}"}
            except Exception as e:
                return {"valid": False, "reason": f"API validation error: {str(e)}"}

    async def list_credentials_for_program(
        self, program_id: UUID
    ) -> list[OpportunityCredential]:
        """
        List all stored credentials for a program (no Vault access).

        Args:
            program_id: Program UUID

        Returns:
            List of OpportunityCredential records
        """
        stmt = (
            select(OpportunityCredential)
            .where(OpportunityCredential.program_id == program_id)
            .order_by(OpportunityCredential.access_type)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_scanning_modes(
        self, program_id: UUID
    ) -> dict[str, Any]:
        """
        Determine available scanning modes based on stored credentials and metadata.

        This returns what scanning modes are POSSIBLE for this program based on:
        1. What access types are enabled in metadata (signup URLs available)
        2. Which credentials are actually stored and active

        Args:
            program_id: Program UUID

        Returns:
            Dict with keys:
                - program_id (str)
                - available_modes (list): ["unauthenticated", "user_account", "api_key", "hunter_account"]
                - warnings (list): [{type, access_type, message, signup_url}, ...]
                - recommendation (str)
        """
        # Load metadata
        meta_stmt = select(OpportunityAccessMetadata).where(
            OpportunityAccessMetadata.program_id == program_id
        )
        meta_result = await self.db.execute(meta_stmt)
        metadata = {m.access_type: m for m in meta_result.scalars().all()}

        # Load stored credentials
        stored = await self.list_credentials_for_program(program_id)
        stored_by_type = {c.access_type: c for c in stored}

        modes = []
        warnings = []

        # Unauthenticated always possible (if enabled in metadata)
        unauth_meta = metadata.get("unauthenticated")
        if unauth_meta is None or bool(unauth_meta.enabled):
            modes.append("unauthenticated")

        # User account
        user_meta = metadata.get("user_account")
        if user_meta and user_meta.enabled:
            if "user_account" in stored_by_type and stored_by_type["user_account"].status == "active":
                modes.append("user_account")
            else:
                warnings.append({
                    "type": "MISSING_CREDENTIALS",
                    "access_type": "user_account",
                    "message": "User account credentials not stored.",
                    "signup_url": user_meta.signup_url,
                    "signup_instructions": user_meta.signup_instructions,
                })

        # API Key
        api_meta = metadata.get("api_key")
        if api_meta and api_meta.enabled:
            if "api_key" in stored_by_type and stored_by_type["api_key"].status == "active":
                modes.append("api_key")
            else:
                warnings.append({
                    "type": "MISSING_CREDENTIALS",
                    "access_type": "api_key",
                    "message": "API key not stored.",
                    "signup_url": api_meta.signup_url,
                    "signup_instructions": api_meta.signup_instructions,
                    "rate_limits": api_meta.rate_limits,
                })

        # Hunter account
        hunter_meta = metadata.get("hunter_account")
        if hunter_meta and hunter_meta.enabled:
            if "hunter_account" in stored_by_type and stored_by_type["hunter_account"].status == "active":
                modes.append("hunter_account")
            else:
                warnings.append({
                    "type": "MISSING_CREDENTIALS",
                    "access_type": "hunter_account",
                    "message": "Hunter account not available.",
                    "signup_url": hunter_meta.signup_url,
                    "signup_instructions": hunter_meta.signup_instructions,
                })

        # Build recommendation
        if not modes or modes == ["unauthenticated"]:
            recommendation = "Only public/unauthenticated scanning available. Store credentials to unlock authenticated testing."
        else:
            recommendation = f"Can scan with {len(modes)} mode(s): {', '.join(modes)}"

        return {
            "program_id": str(program_id),
            "available_modes": modes,
            "warnings": warnings,
            "recommendation": recommendation,
        }

    async def upsert_access_metadata(
        self,
        program_id: UUID,
        access_type: str,
        enabled: bool = True,
        signup_url: str | None = None,
        signup_instructions: str | None = None,
        requires_email: bool = False,
        requires_payment: bool = False,
        rate_limits: str | None = None,
        available_endpoints: str | None = None,
        testing_account_available: bool = False,
        testing_account_url: str | None = None,
        testing_instructions: str | None = None,
    ) -> OpportunityAccessMetadata:
        """
        Create or update access metadata for a program.

        Args:
            program_id: Program UUID
            access_type: Type of access
            enabled: Is this access type available?
            signup_url: URL to sign up
            signup_instructions: How to sign up
            requires_email: Does signup require email?
            requires_payment: Does it cost money?
            rate_limits: Rate limit info
            available_endpoints: Available API endpoints (JSON string or list)
            testing_account_available: Is a test account provided?
            testing_account_url: URL for test account
            testing_instructions: How to get test account

        Returns:
            OpportunityAccessMetadata record
        """
        stmt = select(OpportunityAccessMetadata).where(
            (OpportunityAccessMetadata.program_id == program_id)
            & (OpportunityAccessMetadata.access_type == access_type)
        )
        result = await self.db.execute(stmt)
        existing = result.scalars().first()

        if existing:
            existing.enabled = enabled
            existing.signup_url = signup_url
            existing.signup_instructions = signup_instructions
            existing.requires_email = requires_email
            existing.requires_payment = requires_payment
            existing.rate_limits = rate_limits
            existing.available_endpoints = available_endpoints
            existing.testing_account_available = testing_account_available
            existing.testing_account_url = testing_account_url
            existing.testing_instructions = testing_instructions
            record = existing
        else:
            record = OpportunityAccessMetadata(
                program_id=program_id,
                access_type=access_type,
                enabled=enabled,
                signup_url=signup_url,
                signup_instructions=signup_instructions,
                requires_email=requires_email,
                requires_payment=requires_payment,
                rate_limits=rate_limits,
                available_endpoints=available_endpoints,
                testing_account_available=testing_account_available,
                testing_account_url=testing_account_url,
                testing_instructions=testing_instructions,
            )
            self.db.add(record)

        await self.db.flush()
        await self.db.commit()
        return record
