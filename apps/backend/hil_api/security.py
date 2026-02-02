import os
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from enum import Enum

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "admin_secret_key_default")
USER_API_KEY = os.getenv("USER_API_KEY", "user_secret_key_default")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class Permission(str, Enum):
    ORCHESTRATE_SCAN = "orchestrate:scan"
    MANAGE_USERS = "manage:users"
    VIEW_AUDIT_LOG = "view:audit_log"
    MANAGE_CONFIG = "manage:config"
    INITIATE_SCAN = "initiate:scan"
    VIEW_FINDINGS = "view:findings"
    SUBMIT_FINDINGS = "submit:submissions"
    VIEW_DASHBOARD = "view:dashboard"

ROLE_PERMISSIONS = {
    UserRole.ADMIN: [p for p in Permission],
    UserRole.USER: [Permission.INITIATE_SCAN, Permission.VIEW_FINDINGS, Permission.SUBMIT_FINDINGS, Permission.VIEW_DASHBOARD],
}

def get_current_user_role(api_key: str = Depends(api_key_header)) -> UserRole:
    if api_key == ADMIN_API_KEY:
        return UserRole.ADMIN
    if api_key == USER_API_KEY:
        return UserRole.USER
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key")

class RBAC:
    def __init__(self, required_permission: Permission):
        self.required_permission = required_permission
    def __call__(self, user_role: UserRole = Depends(get_current_user_role)):
        if self.required_permission not in ROLE_PERMISSIONS.get(user_role, []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission denied. Requires: {self.required_permission.value}")
        return True
