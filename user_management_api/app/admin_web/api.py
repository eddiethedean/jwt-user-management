from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.admin_web.auth import require_admin_session
from app.admin_web.csrf import require_csrf
from app.api.deps import get_db
from app.api.routes_users import list_users, update_user
from app.api.routes_invites import create_invite
from app.models.invite import InviteCreate
from app.models.user import User, UserUpdate
from app.schemas.invites import InviteCreateResponse


router = APIRouter(prefix="/admin/api", tags=["admin-web-api"])


def _admin_user_dict(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "is_active": u.is_active,
        "is_admin": u.is_admin,
        "email_verified": u.email_verified,
        "permissions": list(u.permissions or []),
        "created_at": getattr(u, "created_at", None),
    }


@router.get("/users")
def admin_list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> list[dict[str, Any]]:
    # Reuse existing handler to keep behavior consistent.
    users = list_users(db=db, x_admin_api_key=None, current_admin=_admin)  # type: ignore[arg-type]
    out: list[dict[str, Any]] = []
    for u in users:
        out.append(_admin_user_dict(u))
    return out


class UserPatch(BaseModel):
    permissions: Optional[list[str]] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


@router.patch("/users/{user_id}")
def admin_patch_user(
    user_id: int,
    payload: UserPatch,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_session),
    _csrf: None = Depends(require_csrf),
) -> dict[str, Any]:
    model_payload = UserUpdate(**payload.model_dump(exclude_unset=True))
    updated = update_user(
        user_id=user_id,
        payload=model_payload,
        db=db,
        x_admin_api_key=None,
        current_admin=admin,
    )
    return {"ok": True, "user": _admin_user_dict(updated)}


@router.post("/invites", response_model=InviteCreateResponse)
async def admin_create_invite(
    payload: "InviteCreate",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_session),
    _csrf: None = Depends(require_csrf),
) -> InviteCreateResponse:
    return await create_invite(
        payload=payload,
        db=db,
        x_admin_api_key=None,
        current_admin=admin,
    )
