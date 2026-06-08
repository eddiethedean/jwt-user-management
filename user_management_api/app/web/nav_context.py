"""Resolve signed-in viewer role for server-rendered HTML navigation."""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.routes.deps import user_from_token
from app.web.session import get_auth_token


async def attach_nav_context(request: Request, db: AsyncSession) -> None:
    """Set ``request.state.session_email`` and ``request.state.is_admin`` for templates."""
    request.state.session_email = None
    request.state.is_admin = False

    token = get_auth_token(request)
    if not token:
        return

    try:
        user = await user_from_token(db=db, token=token)
    except HTTPException:
        return

    request.state.session_email = user.email
    request.state.is_admin = bool(getattr(user, "is_admin", False))
