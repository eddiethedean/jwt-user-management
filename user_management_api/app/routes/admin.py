from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.roles import (
    apply_user_roles,
    effective_user_roles,
    normalize_selected_roles,
    roles_for_admin_flag,
)
from app.db import get_db
from app.models import User
from app.routes.deps import admin_from_bearer, bearer_scheme
from app.schemas.admin import AdminUpdateUserRequest
from app.user_profile import user_command_field_enabled, user_to_api_dict


router = APIRouter(tags=["admin"])


@router.patch("/admin/users/{user_id}")
async def admin_api_update_user(
    user_id: int,
    payload: AdminUpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin = await admin_from_bearer(db=db, creds=creds)
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    fields_set = payload.model_fields_set
    current_roles = effective_user_roles(user, settings.user_roles)

    if user.id == admin.id:
        if "is_active" in fields_set and payload.is_active != bool(user.is_active):
            raise HTTPException(
                status_code=400,
                detail="You can’t modify your own role/status here",
            )
        if "is_admin" in fields_set and payload.is_admin != bool(user.is_admin):
            raise HTTPException(
                status_code=400,
                detail="You can’t modify your own role/status here",
            )
        if "roles" in fields_set:
            next_roles = normalize_selected_roles(
                payload.roles or [], settings.user_roles
            )
            if next_roles != current_roles:
                raise HTTPException(
                    status_code=400,
                    detail="You can’t modify your own role/status here",
                )

    if "full_name" in fields_set:
        fn = str(payload.full_name or "").strip() or None
        user.full_name = fn
    if "is_active" in fields_set and payload.is_active is not None:
        user.is_active = payload.is_active
    if "roles" in fields_set:
        apply_user_roles(
            user,
            payload.roles or [],
            allowed_roles=settings.user_roles,
            admin_roles=settings.admin_roles,
        )
    elif "is_admin" in fields_set and payload.is_admin is not None:
        apply_user_roles(
            user,
            roles_for_admin_flag(
                payload.is_admin,
                allowed_roles=settings.user_roles,
                admin_roles=settings.admin_roles,
            ),
            allowed_roles=settings.user_roles,
            admin_roles=settings.admin_roles,
        )
    if user_command_field_enabled() and "command" in fields_set:
        user.command = str(payload.command or "").strip() or None

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"ok": True, "user": user_to_api_dict(user)}


@router.delete("/admin/users/{user_id}")
async def admin_api_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    admin = await admin_from_bearer(db=db, creds=creds)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="You can’t delete your own account")
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"ok": True}


## HTML admin UI routes live in ``html_admin.py`` when ``HTML_UI_ENABLED`` is true.
