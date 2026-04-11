"""
FastAPI router for Vault secret management endpoints.

Provides HTTP endpoints for storing, retrieving, validating, and rotating
secrets with HashiCorp Vault. All operations require proper RBAC permissions.

Never logs or exposes secret values in responses or error messages.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from apps.backend.src.auth.security import get_current_user
from apps.backend.src.core.hil_security import (
    assert_permission,
    Permission,
    User,
)
from apps.backend.src.core.vault_client import (
    VaultClient,
    VaultException,
    VaultConnectionError,
    SecretNotFoundError,
)
from apps.backend.src.models.vault_models import (
    StoreSecretRequest,
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

    if not request.name or not request.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="name and value are required"
        )

    secret_path = f"secret/data/kaison/{request.name.lower()}"

    try:
        secret_data = {
            "value": request.value,
            "type": request.type,
        }
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
            last_updated=None,
            environment="production",
        )

    except VaultException as e:
        logger.error(f"Failed to store secret {request.name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to store secret: {str(e)}"
        )


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
