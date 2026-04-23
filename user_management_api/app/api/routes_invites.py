from pathlib import Path
from typing import Any, Optional

from app.services.azure_ad import AzureADUser
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import update
from sqlmodel import Session, select
from starlette.requests import Request

from app.api.deps import get_db, get_optional_admin, require_admin_api_key
from app.core.config import settings
from app.core.security import hash_password
from app.models.invite import InviteCreate, InviteToken
from app.models.user import User
from app.schemas.invites import (
    InviteAcceptRequest,
    InviteAcceptResponse,
    InviteCreateResponse,
)
from app.security.origin import require_same_origin
from app.services.azure_ad import validate_email_in_tenant
from app.services.emailer import send_invite_email


router = APIRouter(prefix="/invites", tags=["invites"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    # SQLite often returns naive datetimes even if you store tz-aware.
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.post("", response_model=InviteCreateResponse)
async def create_invite(
    payload: InviteCreate,
    db: Session = Depends(get_db),
    x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-Api-Key"),
    current_admin: Optional[User] = Depends(get_optional_admin),
) -> InviteCreateResponse:
    if x_admin_api_key is not None:
        require_admin_api_key(x_admin_api_key)
        invited_by = None
    elif current_admin:
        invited_by: Optional[int] = current_admin.id
    else:
        raise HTTPException(status_code=403, detail="Admin required")

    azure_enabled = bool(
        settings.azure_tenant_id
        and settings.azure_client_id
        and settings.azure_client_secret
    )
    if azure_enabled:
        ad_user: Optional[AzureADUser] = await validate_email_in_tenant(payload.email)
        if ad_user is None:
            raise HTTPException(
                status_code=400, detail="Email not found in Azure AD tenant"
            )

    token: str = secrets.token_urlsafe(32)
    token_hash: str = _hash_token(token)
    now: datetime = datetime.now(timezone.utc)
    expires_at: datetime = now + timedelta(days=7)

    invite = InviteToken(
        email=payload.email,
        full_name=payload.full_name,
        is_admin=payload.is_admin,
        permissions=payload.permissions,
        token_hash=token_hash,
        invited_by_user_id=invited_by,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    base: str = (settings.public_base_url or "http://localhost:8000").rstrip("/")
    invite_url: str = f"{base}/invites/accept?token={token}"
    send_invite_email(to_email=payload.email, invite_url=invite_url)

    return InviteCreateResponse(ok=True, invite_url=invite_url, expires_at=expires_at)


async def _accept_invite(
    *, token: str, password: str, full_name: Optional[str], db: Session
) -> InviteAcceptResponse:
    token_hash: str = _hash_token(token)
    invite: Optional[InviteToken] = db.exec(
        select(InviteToken).where(InviteToken.token_hash == token_hash)
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    now: datetime = datetime.now(timezone.utc)
    if _as_utc(invite.expires_at) < now:
        raise HTTPException(status_code=400, detail="Invite expired")

    # Single-use enforcement (atomic): mark invite as used only if unused and unexpired.
    res = db.exec(
        update(InviteToken)
        # `InviteToken.token_hash` is a SQLModel field; mypy/ty may see it as `str`.
        # Use SQLAlchemy `Column` access for typed SQL expressions.
        .where(getattr(InviteToken, "__table__").c.token_hash == token_hash)
        .where(getattr(InviteToken, "__table__").c.used_at.is_(None))
        .where(getattr(InviteToken, "__table__").c.expires_at >= now)
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if getattr(res, "rowcount", 0) != 1:
        refreshed: Optional[InviteToken] = db.exec(
            select(InviteToken).where(InviteToken.token_hash == token_hash)
        ).first()
        if not refreshed:
            raise HTTPException(status_code=404, detail="Invite not found")
        if refreshed.used_at is not None:
            raise HTTPException(status_code=400, detail="Invite already used")
        if _as_utc(refreshed.expires_at) < now:
            raise HTTPException(status_code=400, detail="Invite expired")
        raise HTTPException(status_code=400, detail="Invite could not be accepted")

    ad_user: Optional[AzureADUser] = await validate_email_in_tenant(invite.email)
    azure_enabled = bool(
        settings.azure_tenant_id
        and settings.azure_client_id
        and settings.azure_client_secret
    )
    if azure_enabled and ad_user is None:
        raise HTTPException(
            status_code=400, detail="Email not found in Azure AD tenant"
        )
    if ad_user is None:
        ad_object_id = None
        email_verified = False
    else:
        ad_object_id: Optional[Any] = getattr(ad_user, "id", None)
        email_verified: bool = True if ad_user else False

    user: Optional[User] = db.exec(
        select(User).where(User.email == invite.email)
    ).first()
    if user:
        user.hashed_password = hash_password(password)
        user.full_name = full_name or invite.full_name or user.full_name
        user.is_admin = bool(invite.is_admin)
        user.permissions = list(invite.permissions or [])
        user.email_verified = email_verified
        user.ad_object_id = ad_object_id
    else:
        user = User(
            email=invite.email,
            full_name=full_name or invite.full_name,
            hashed_password=hash_password(password),
            is_active=True,
            is_admin=bool(invite.is_admin),
            permissions=list(invite.permissions or []),
            email_verified=email_verified,
            ad_object_id=ad_object_id,
        )
        db.add(user)

    db.commit()

    return InviteAcceptResponse(ok=True, email_verified=email_verified)


@router.post("/accept", response_model=InviteAcceptResponse)
async def accept_invite(
    payload: InviteAcceptRequest,
    db: Session = Depends(get_db),
) -> InviteAcceptResponse:
    return await _accept_invite(
        token=payload.token,
        password=payload.password,
        full_name=payload.full_name,
        db=db,
    )


@router.get("/accept", response_class=HTMLResponse)
def accept_invite_page(request: Request, token: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "accept_invite.html", {"request": request, "token": token}
    )


@router.post("/accept-form", response_class=HTMLResponse)
async def accept_invite_form(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    full_name: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        require_same_origin(request)
    except ValueError:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    try:
        await _accept_invite(token=token, password=password, full_name=full_name, db=db)
    except HTTPException as e:
        return templates.TemplateResponse(
            request,
            "accept_invite.html",
            {"request": request, "token": token, "error": e.detail},
            status_code=e.status_code,
        )
    return templates.TemplateResponse(
        request,
        "accept_invite.html",
        {"request": request, "token": token, "success": True},
    )
