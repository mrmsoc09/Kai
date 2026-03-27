from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy import select

from apps.backend.src.auth.models import Tenant, User, UserRole
from apps.backend.src.auth.utils import hash_password
from apps.backend.src.core.hil_db import get_async_session_maker

logger = logging.getLogger(__name__)


def _env_truthy(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _bootstrap_enabled() -> bool:
    # Requires explicit opt-in via K1_BOOTSTRAP_ADMIN_ENABLED=true in every
    # environment.  Defaulting to True in non-production created a persistent
    # empty-password admin account on every staging/CI instance.
    return _env_truthy("K1_BOOTSTRAP_ADMIN_ENABLED", False)


async def ensure_bootstrap_admin_user() -> None:
    """
    Ensure a local bootstrap admin user exists.

    The user is created with an empty-password hash and must_change_password=true,
    so first login requires setting a real password before normal platform access.
    """
    if not _bootstrap_enabled():
        return

    username = (os.getenv("K1_BOOTSTRAP_ADMIN_USERNAME", "k1-admin") or "").strip()
    tenant_name = (os.getenv("K1_BOOTSTRAP_TENANT_NAME", "kai-local") or "").strip()
    if not username or not tenant_name:
        logger.warning("Bootstrap admin is enabled but username/tenant name is empty; skipping user bootstrap.")
        return

    session_maker = get_async_session_maker()
    async with session_maker() as db:
        result = await db.execute(select(User).where(User.username == username))
        existing_user = result.scalar_one_or_none()
        if existing_user is not None:
            return

        tenant_result = await db.execute(select(Tenant).where(Tenant.name == tenant_name))
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(
                id=uuid.uuid4(),
                name=tenant_name,
                is_active=True,
                config_json={},
            )
            db.add(tenant)
            await db.flush()

        bootstrap_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            username=username,
            hashed_password=hash_password(""),
            email=None,
            full_name="Kai Local Admin",
            is_active=True,
            is_superuser=True,
            must_change_password=True,
            role=UserRole.ADMIN,
        )
        db.add(bootstrap_user)
        await db.commit()
        logger.warning(
            "Created bootstrap admin user '%s' with empty initial password; password setup is required on first login.",
            username,
        )
