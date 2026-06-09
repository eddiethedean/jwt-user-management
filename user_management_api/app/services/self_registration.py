from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.core.config as app_config
from app.invite_email_domains import invite_email_domain_allowed
from app.models import InviteToken, User
from app.routes.email_links import external_accept_invite_url
from app.services.directory import lookup_email
from app.services.email import send_self_registration_email


@dataclass(frozen=True)
class RegisterResult:
    ok: bool
    setup_url: str = ""
    email_sent: bool = False
    error: str | None = None


def _expose_setup_url() -> bool:
    return bool(getattr(app_config._defaults, "EXPOSE_SETUP_URLS_IN_RESPONSE", False))


async def register_email_for_setup(
    *,
    request: Request,
    email: str,
    db: AsyncSession,
) -> RegisterResult:
    email_n = (email or "").strip().lower()
    if not email_n:
        return RegisterResult(ok=False, error="Email is required")

    existing = (await db.exec(select(User).where(User.email == email_n))).first()
    if existing:
        return RegisterResult(ok=True, email_sent=False)

    if not invite_email_domain_allowed(email_n):
        return RegisterResult(
            ok=False,
            error="Email domain is not allowed for registration",
        )

    if app_config.settings.registration_directory_applies_to_email(email_n):
        rec = None
        try:
            rec = lookup_email(email_n)
        except Exception:
            if app_config.settings.registration_directory_lookup_required:
                return RegisterResult(ok=False, error="Directory lookup failed")
            rec = None
        if app_config.settings.registration_directory_lookup_required and not rec:
            return RegisterResult(ok=False, error="Email not found in directory")

    now = datetime.now(timezone.utc)
    from app.routes.invites import invalidate_unused_invites_for_email

    await invalidate_unused_invites_for_email(db=db, email=email_n, now=now)
    raw = InviteToken.new_raw_token()
    invite = InviteToken(
        email=email_n,
        token_hash=InviteToken.hash_token(raw),
        created_at=now,
        expires_at=now + timedelta(hours=2),
        used_at=None,
        grant_admin=False,
    )
    db.add(invite)
    await db.commit()

    setup_url = external_accept_invite_url(request, token=raw)
    email_sent = False
    if app_config.settings.smtp_host and app_config.settings.smtp_from_email:
        try:
            send_self_registration_email(to_email=email_n, setup_url=setup_url)
            email_sent = True
        except Exception:
            pass

    exposed_url = setup_url if _expose_setup_url() else ""
    return RegisterResult(ok=True, setup_url=exposed_url, email_sent=email_sent)
