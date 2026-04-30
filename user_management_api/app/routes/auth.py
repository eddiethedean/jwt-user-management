from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from fastapi_workbench import base_path, safe_redirect
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models import User
from app.web.session import clear_auth_cookie, set_auth_cookie


router = APIRouter(tags=["auth"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)


def _norm_email(v: str) -> str:
    return (v or "").strip().lower()


@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
def register_page(request: Request) -> HTMLResponse:
    bp = base_path(request)
    return templates.TemplateResponse(
        request, "register.html", {"request": request, "base_path": bp}
    )


@router.post("/register", response_class=HTMLResponse, include_in_schema=False)
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    bp = base_path(request)
    email_n = _norm_email(email)
    if not email_n or not password:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "request": request,
                "error": "Email and password are required",
                "base_path": bp,
            },
            status_code=400,
        )

    existing: Optional[User] = db.exec(
        select(User).where(User.email == email_n)
    ).first()
    if existing:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"request": request, "error": "Email already exists", "base_path": bp},
            status_code=400,
        )

    user = User(email=email_n, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "success": "Account created. Please sign in.",
            "base_path": bp,
        },
    )


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request) -> HTMLResponse:
    bp = base_path(request)
    return templates.TemplateResponse(
        request, "login.html", {"request": request, "base_path": bp}
    )


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    bp = base_path(request)
    email_n = _norm_email(email)
    user: Optional[User] = db.exec(select(User).where(User.email == email_n)).first()
    if (
        not user
        or not getattr(user, "is_active", True)
        or not verify_password(password, user.hashed_password)
    ):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "Invalid email or password", "base_path": bp},
            status_code=400,
        )
    token = create_access_token(subject=str(user.id))
    resp = templates.TemplateResponse(
        request,
        "token.html",
        {"request": request, "token": token, "email": user.email, "base_path": bp},
    )
    set_auth_cookie(resp, request=request, token=token)
    return resp


@router.post("/logout", include_in_schema=False)
def logout(request: Request) -> Response:
    resp = safe_redirect(request, "/login", status_code=303)
    clear_auth_cookie(resp, request=request)
    return resp


@router.post("/auth/token")
def token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict:
    username = _norm_email(form.username)
    user: Optional[User] = db.exec(select(User).where(User.email == username)).first()
    if (
        not user
        or not getattr(user, "is_active", True)
        or not verify_password(form.password, user.hashed_password)
    ):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}
