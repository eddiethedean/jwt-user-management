from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from sqlmodel import Session, select
from starlette.requests import Request

from app.api.deps import get_db
from app.models.user import User


def get_admin_session_user_id(request: Request) -> Optional[int]:
    raw = (request.session or {}).get("admin_user_id")  # type: ignore[attr-defined]
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def require_admin_session(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user_id = get_admin_session_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = db.exec(select(User).where(User.id == user_id)).first()
    if not user or not user.is_active or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user
