from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.security import create_access_token, decode_token, verify_password
from app.db import get_db
from app.models import User


router = APIRouter(tags=["admin"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

ADMIN_EMAIL = (os.getenv("SEED_ADMIN_EMAIL") or "admin@example.com").strip().lower()


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page(
    request: Request,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    if not token:
        return RedirectResponse(url=f"{bp}/admin/login", status_code=303)
    try:
        payload: dict[str, Any] = decode_token(token)
        user_id = int(payload.get("sub") or 0)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    if user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required")

    users = db.exec(select(User).order_by(text("id"))).all()
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "users": users,
            "email": user.email,
            "token": token,
            "base_path": bp,
        },
    )


@router.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
def admin_login_page(request: Request) -> HTMLResponse:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {"request": request, "admin_email": ADMIN_EMAIL, "base_path": bp},
    )


@router.post("/admin/login", response_class=HTMLResponse, include_in_schema=False)
def admin_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    email_n = (email or "").strip().lower()
    user: Optional[User] = db.exec(select(User).where(User.email == email_n)).first()
    if (
        not user
        or user.email != ADMIN_EMAIL
        or not verify_password(password, user.hashed_password)
    ):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "request": request,
                "error": "Invalid credentials",
                "admin_email": ADMIN_EMAIL,
                "base_path": bp,
            },
            status_code=400,
        )

    token = create_access_token(subject=str(user.id))
    return RedirectResponse(url=f"{bp}/admin?token={token}", status_code=303)
