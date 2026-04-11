from __future__ import annotations

from enum import Enum

from fastapi import Depends, HTTPException, status

from .auth import (
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    User,
    get_current_user,
)


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(str, Enum):
    ORCHESTRATE_SCAN = "orchestrate:scan"
    MANAGE_USERS = "manage:users"
    VIEW_AUDIT_LOG = "view:audit_log"
    VIEW_CONFIG = "view:config"
    MANAGE_CONFIG = "manage:config"
    DELETE_CONFIG = "delete:config"
    INITIATE_SCAN = "initiate:scan"
    VIEW_FINDINGS = "view:findings"
    SUBMIT_FINDINGS = "submit:submissions"
    VIEW_DASHBOARD = "view:dashboard"


ROLE_PERMISSIONS: dict[UserRole, list[Permission]] = {
    UserRole.ADMIN: list(Permission),
    UserRole.OPERATOR: [
        Permission.INITIATE_SCAN,
        Permission.VIEW_FINDINGS,
        Permission.SUBMIT_FINDINGS,
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AUDIT_LOG,
        Permission.VIEW_CONFIG,
    ],
    UserRole.ANALYST: [
        Permission.VIEW_FINDINGS,
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AUDIT_LOG,
        Permission.VIEW_CONFIG,
    ],
    UserRole.VIEWER: [
        Permission.VIEW_FINDINGS,
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_CONFIG,
    ],
}

# Map auth-layer role strings to hil_security UserRole
_ROLE_MAP: dict[str, UserRole] = {
    ROLE_ADMIN: UserRole.ADMIN,
    ROLE_OPERATOR: UserRole.OPERATOR,
    ROLE_ANALYST: UserRole.ANALYST,
    ROLE_VIEWER: UserRole.VIEWER,
}

# Priority order (highest first) for resolving effective role from a multi-role token
_ROLE_PRIORITY = [UserRole.ADMIN, UserRole.OPERATOR, UserRole.ANALYST, UserRole.VIEWER]


def get_current_user_role(user: User = Depends(get_current_user)) -> UserRole:
    """Return the highest-privilege role held by the authenticated user."""
    held = {_ROLE_MAP[r] for r in user.roles if r in _ROLE_MAP}
    for role in _ROLE_PRIORITY:
        if role in held:
            return role
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_roles")


class RBAC:
    def __init__(self, required_permission: Permission):
        self.required_permission = required_permission

    def __call__(self, user_role: UserRole = Depends(get_current_user_role)) -> bool:
        if self.required_permission not in ROLE_PERMISSIONS.get(user_role, []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Requires: {self.required_permission.value}",
            )
        return True
