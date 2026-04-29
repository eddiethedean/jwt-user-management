from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from jose import JWTError
from sqlmodel import Session, select

from app.core.security import decode_token
from app.db import get_db
from app.models import User


router = APIRouter(tags=["users"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
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
    user: Optional[User] = db.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/users/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "created_at": current_user.created_at,
    }


@router.get("/users", response_class=Response)
def users(
    request: Request,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Response:
    """
    One route with two modes:\n+    - HTML mode: provide `?token=...`.\n+    - JSON mode: provide `Authorization: Bearer <token>`.\n+    """
    if token:
        try:
            payload: dict[str, Any] = decode_token(token)
            user_id = int(payload.get("sub") or 0)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.exec(select(User).where(User.id == user_id)).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        users = db.exec(select(User).order_by(User.id)).all()
        return templates.TemplateResponse(
            request,
            "users.html",
            {"request": request, "users": users, "email": user.email, "token": token},
        )

    if not creds:
        raise HTTPException(
            status_code=401,
            detail="Provide Authorization: Bearer <token> (or use /users?token=... for HTML)",
        )
    _ = get_current_user(db=db, creds=creds)
    users = db.exec(select(User).order_by(User.id)).all()
    return JSONResponse(
        content=[
            {"id": u.id, "email": u.email, "created_at": u.created_at.isoformat()}
            for u in users
        ]
    )

