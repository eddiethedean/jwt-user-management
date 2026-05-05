from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from jose import JWTError
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi_workbench import base_path, safe_redirect
from app.core.security import decode_token
from app.db import get_db
from app.models import User
from app.web.session import get_auth_token, set_auth_cookie


router = APIRouter(tags=["users"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload: dict[str, Any] = decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user: Optional[User] = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/users/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "created_at": current_user.created_at,
    }


@router.get("/users", response_class=Response)
async def users(
    request: Request,
    token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Response:
    """
    One route with two modes:\n+    - HTML mode: uses the HttpOnly cookie (or legacy `?token=...`).\n+    - JSON mode: provide `Authorization: Bearer <token>`.\n+"""
    bp = base_path(request)

    if token:
        # Promote legacy/demo URL token into the cookie and clean up the URL.
        try:
            payload: dict[str, Any] = decode_token(token)
            user_id = int(payload.get("sub") or 0)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = (await db.exec(select(User).where(User.id == user_id))).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        resp = safe_redirect(request, "/users", status_code=303)
        set_auth_cookie(resp, request=request, token=token)
        return resp

    cookie_token = get_auth_token(request)
    if cookie_token:
        try:
            payload = decode_token(cookie_token)
            user_id = int(payload.get("sub") or 0)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = (await db.exec(select(User).where(User.id == user_id))).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        users = (await db.exec(select(User).order_by(text("id")))).all()
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "request": request,
                "users": users,
                "email": user.email,
                "is_admin": bool(getattr(user, "is_admin", False)),
                "base_path": bp,
            },
        )

    if not creds:
        raise HTTPException(
            status_code=401,
            detail="Provide Authorization: Bearer <token>",
        )
    _ = await get_current_user(db=db, creds=creds)
    users = (await db.exec(select(User).order_by(text("id")))).all()
    return JSONResponse(
        content=[
            {"id": u.id, "email": u.email, "created_at": u.created_at.isoformat()}
            for u in users
        ]
    )
