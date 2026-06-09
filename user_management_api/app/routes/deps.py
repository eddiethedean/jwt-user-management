from __future__ import annotations

from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.jwt_principal import (
    JwtPrincipal,
    load_user_by_id,
    principal_from_bearer,
    require_admin_principal,
)
from app.db import get_db
from app.models import User


bearer_scheme = HTTPBearer(auto_error=False)


def principal_from_bearer_creds(
    creds: Optional[HTTPAuthorizationCredentials],
) -> JwtPrincipal:
    return principal_from_bearer(creds)


def admin_principal_from_bearer(
    creds: Optional[HTTPAuthorizationCredentials],
) -> JwtPrincipal:
    return require_admin_principal(principal_from_bearer(creds))


async def user_from_bearer(
    *, db: AsyncSession, creds: Optional[HTTPAuthorizationCredentials]
) -> User:
    """Load User row for endpoints that need DB fields (password hash, profile)."""
    principal = principal_from_bearer(creds)
    return await load_user_by_id(db=db, user_id=principal.user_id)


async def admin_from_bearer(
    *, db: AsyncSession, creds: Optional[HTTPAuthorizationCredentials]
) -> User:
    principal = admin_principal_from_bearer(creds)
    return await load_user_by_id(db=db, user_id=principal.user_id)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    return await user_from_bearer(db=db, creds=creds)


async def get_current_principal(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> JwtPrincipal:
    return principal_from_bearer(creds)
