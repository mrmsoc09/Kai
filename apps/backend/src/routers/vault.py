"""
FastAPI router for Vault secret management endpoints.

Provides HTTP endpoints for storing, retrieving, validating, and rotating
secrets with HashiCorp Vault. All operations require proper RBAC permissions.

Never logs or exposes secret values in responses or error messages.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from apps.backend.src.core.auth import get_current_user, User
from apps.backend.src.core.hil_security import (
    Permission,
    RBAC,
    ROLE_PERMISSIONS,
    get_current_user_role,
    UserRole,
)
from apps.backend.src.core.vault_client import (
    VaultClient,
    VaultException,
    VaultConnectionError,
    SecretNotFoundError,
)
from apps.backend.src.models.vault_models import (
    StoreSecretRequest,
    StoreNetworkCredentialRequest,
    SecretResponse,
    ListSecretsResponse,
    SecretMetadataResponse,
    TestSecretRequest,
    TestSecretResponse,
    RotateSecretRequest,
    RotateSecretResponse,
    SyncSecretsResponse,
    VaultHealthResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vault", tags=["vault"])
_NETWORK_PROVIDER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


def assert_permission(user: User, required_permission: Permission) -> None:
    """Check if user has required permission, raise HTTPException if not."""
    # Map user roles to hil_security UserRole
    from apps.backend.src.core.hil_security import _ROLE_MAP

    user_roles = [_ROLE_MAP.get(role) for role in user.roles if role in _ROLE_MAP]
    if not user_roles:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid roles found in token",
        )

    # Check if any of user's roles have the required permission
    for role in user_roles:
        if required_permission in ROLE_PERMISSIONS.get(role, []):
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Permission denied. Requires: {required_permission.value}",
    )


# Global vault client instance
_vault_client: Optional[VaultClient] = None


def get_vault_client() -> VaultClient:
    """Dependency to get vault client instance."""
    global _vault_client
    if _vault_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vault client not initialized"
        )
    return _vault_client


def init_vault_client(
    vault_addr: str = None,
    vault_token: str = None,
    vault_namespace: str = None,
) -> VaultClient:
    """Initialize and return vault client."""
    global _vault_client
    _vault_client = VaultClient(
        vault_addr=vault_addr,
        vault_token=vault_token,
        vault_namespace=vault_namespace,
    )
    return _vault_client


@router.get("/health", response_model=VaultHealthResponse)
async def get_vault_health(vault: VaultClient = Depends(get_vault_client)):
    """Check Vault server health and connectivity."""
    try:
        health = vault.health_check()
        return VaultHealthResponse(
            connected=True,
            status="ready" if health.get("initialized") and not health.get("sealed") else "sealed",
            version=health.get("version"),
            sealed=health.get("sealed"),
            initialized=health.get("initialized"),
            standby=health.get("standby"),
            cluster_name=health.get("cluster_name"),
        )
    except VaultConnectionError as e:
        logger.warning(f"Vault health check failed: {str(e)}")
        return VaultHealthResponse(
            connected=False,
            status="unavailable",
            version=None,
        )


@router.get("/secrets/list", response_model=ListSecretsResponse)
async def list_secrets(
    prefix: str = "secret/data/kaison",
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """List all secret names under given prefix. Requires VIEW_CONFIG permission."""
    assert_permission(user, Permission.VIEW_CONFIG)

    try:
        secrets = vault.list_secrets(prefix)
        return ListSecretsResponse(secrets=secrets, count=len(secrets))
    except VaultConnectionError as e:
        logger.error(f"Failed to list secrets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vault connection failed"
        )


@router.post("/secrets/store", response_model=SecretResponse)
async def store_secret(
    request: StoreSecretRequest,
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """Store a new secret in Vault. Requires MANAGE_CONFIG permission."""
    assert_permission(user, Permission.MANAGE_CONFIG)

    request_value = (request.value or "").strip()
    request_fields = {
        key: value.strip()
        for key, value in (request.fields or {}).items()
        if isinstance(value, str) and value.strip()
    }

    if not request.name or (not request_value and not request_fields):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name and one of value or fields are required",
        )

    secret_path = f"secret/data/kaison/{request.name.lower()}"

    try:
        secret_data = {
            "type": request.type,
        }
        if request_value:
            secret_data["value"] = request_value
        if request_fields:
            secret_data.update(request_fields)
        if request.description:
            secret_data["description"] = request.description
        if request.tags:
            secret_data["tags"] = ",".join(request.tags)

        vault.write_secret(secret_path, secret_data, overwrite=False)
        logger.info(f"User {user.username} stored secret {request.name}")

        return SecretResponse(
            name=request.name,
            type=request.type,
            status="stored",
            last_updated=datetime.now(timezone.utc),
            environment="production",
        )

    except VaultException as e:
        logger.error(f"Failed to store secret {request.name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to store secret: {str(e)}"
        )


@router.post("/network/providers/{provider_id}/credentials", response_model=SecretResponse)
async def store_network_provider_credentials(
    provider_id: str,
    request: StoreNetworkCredentialRequest,
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """Store structured VPN/proxy credentials for network egress automation."""
    assert_permission(user, Permission.MANAGE_CONFIG)

    provider_norm = provider_id.strip().lower()
    if not _NETWORK_PROVIDER_ID_RE.match(provider_norm):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provider_id must match [a-z0-9][a-z0-9_-]{1,63}",
        )

    secret_fields = {
        "username": (request.username or "").strip(),
        "password": (request.password or "").strip(),
        "pat": (request.pat or "").strip(),
        "api_key": (request.api_key or "").strip(),
        "endpoint": (request.endpoint or "").strip(),
        "proxy_url": (request.proxy_url or "").strip(),
        "notes": (request.notes or "").strip(),
    }
    secret_data = {key: value for key, value in secret_fields.items() if value}

    if not secret_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one credential field is required",
        )

    has_auth_material = any(
        secret_data.get(key)
        for key in ("username", "password", "pat", "api_key", "proxy_url")
    )
    if not has_auth_material:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one auth field (username/password/pat/api_key/proxy_url) is required",
        )

    secret_data["type"] = "network_credential"
    secret_path = f"secret/data/kaison/network/{provider_norm}"

    try:
        vault.write_secret(secret_path, secret_data, overwrite=True)
        logger.info("User %s stored network credentials for provider=%s", user.username, provider_norm)
        return SecretResponse(
            name=f"network/{provider_norm}",
            type="network_credential",
            status="stored",
            last_updated=datetime.now(timezone.utc),
            environment="production",
        )
    except VaultException as e:
        logger.error("Failed to store network credential %s: %s", provider_norm, str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to store network credential: {str(e)}",
        )


@router.get("/network/providers/status")
async def list_network_provider_status(
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """Return configured VPN/proxy provider ids under the network credential namespace."""
    assert_permission(user, Permission.VIEW_CONFIG)
    base_prefix = "secret/data/kaison/network"
    provider_ids = [key.rstrip("/") for key in vault.list_secrets(base_prefix)]
    provider_ids = sorted({provider_id for provider_id in provider_ids if provider_id})
    return {"count": len(provider_ids), "providers": provider_ids}


@router.get("/secrets/{secret_name}/metadata", response_model=SecretMetadataResponse)
async def get_secret_metadata(
    secret_name: str,
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """Get secret metadata without exposing value. Requires VIEW_CONFIG permission."""
    assert_permission(user, Permission.VIEW_CONFIG)

    secret_path = f"secret/data/kaison/{secret_name.lower()}"

    try:
        metadata = vault.get_secret_metadata(secret_path)
        return SecretMetadataResponse(name=secret_name, **metadata)
    except SecretNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret {secret_name} not found"
        )
    except VaultException as e:
        logger.error(f"Failed to get metadata for {secret_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve secret metadata",
        )


@router.delete("/secrets/{secret_name}")
async def delete_secret(
    secret_name: str,
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """Delete a secret from Vault. Requires DELETE_CONFIG permission."""
    assert_permission(user, Permission.DELETE_CONFIG)

    secret_path = f"secret/data/kaison/{secret_name.lower()}"

    try:
        vault.delete_secret(secret_path)
        logger.warning(f"User {user.username} deleted secret {secret_name}")

        return {"success": True, "message": f"Secret {secret_name} deleted successfully"}

    except SecretNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret {secret_name} not found"
        )
    except VaultException as e:
        logger.error(f"Failed to delete secret {secret_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete secret"
        )


@router.post("/secrets/test", response_model=TestSecretResponse)
async def test_secret(
    request: TestSecretRequest,
    user: User = Depends(get_current_user),
):
    """Test if a secret works for its service before storing."""
    vault_client = _vault_client
    if not vault_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vault client not available"
        )

    try:
        is_valid, error_msg = vault_client.validate_secret(request.service, request.value)

        if is_valid:
            logger.info(f"Secret validation successful for service {request.service}")
            return TestSecretResponse(
                valid=True, message=f"{request.service} secret is valid", details={}
            )
        else:
            logger.warning(f"Secret validation failed for {request.service}: {error_msg}")
            return TestSecretResponse(
                valid=False,
                message=f"{request.service} secret validation failed",
                details={"error": error_msg},
            )

    except Exception as e:
        logger.error(f"Error testing secret: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to test secret"
        )


@router.post("/secrets/{secret_name}/rotate", response_model=RotateSecretResponse)
async def rotate_secret(
    secret_name: str,
    request: RotateSecretRequest,
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """Rotate a secret to a new value. Requires MANAGE_CONFIG permission."""
    assert_permission(user, Permission.MANAGE_CONFIG)

    secret_path = f"secret/data/kaison/{secret_name.lower()}"

    try:
        vault.rotate_secret(secret_path, request.new_value)
        logger.warning(f"User {user.username} rotated secret {secret_name}")

        return RotateSecretResponse(
            success=True, message=f"Secret {secret_name} rotated successfully"
        )

    except SecretNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Secret {secret_name} not found"
        )
    except VaultException as e:
        logger.error(f"Failed to rotate secret {secret_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to rotate secret"
        )


@router.get("/secrets/{secret_name}/audit")
async def get_secret_audit_log(
    secret_name: str,
    limit: int = 100,
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """Get audit log for a specific secret. Requires VIEW_CONFIG permission."""
    assert_permission(user, Permission.VIEW_CONFIG)

    secret_path = f"secret/data/kaison/{secret_name.lower()}"

    try:
        audit_log = vault.get_secret_audit_log(secret_path, limit=limit)

        return {"secret": secret_name, "entries": audit_log, "total": len(audit_log)}

    except VaultException as e:
        logger.error(f"Failed to get audit log for {secret_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve audit log"
        )


@router.post("/secrets/sync", response_model=SyncSecretsResponse)
async def sync_secrets_to_environment(
    user: User = Depends(get_current_user),
    vault: VaultClient = Depends(get_vault_client),
):
    """Manually sync all secrets from Vault to environment variables. Requires MANAGE_CONFIG permission."""
    assert_permission(user, Permission.MANAGE_CONFIG)

    try:
        synced_count = vault.sync_secrets_to_env()
        logger.info(f"User {user.username} synced {synced_count} secrets to environment")

        return SyncSecretsResponse(
            success=True,
            synced_count=synced_count,
            message=f"Successfully synced {synced_count} secrets to environment",
        )

    except VaultException as e:
        logger.error(f"Failed to sync secrets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to sync secrets"
        )
