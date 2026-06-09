"""Mount built-in HTML UI routes and static assets when enabled in config."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import app.core.config as app_config


_APP_WEB = Path(__file__).resolve().parent


def include_html_ui(app: FastAPI) -> None:
    if not app_config.settings.html_ui_enabled:
        return

    static_dir = _APP_WEB / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    from app.routes.html_account import router as html_account_router
    from app.routes.html_admin import router as html_admin_router
    from app.routes.html_auth import router as html_auth_router
    from app.routes.html_invites import router as html_invites_router
    from app.routes.html_password import router as html_password_router

    for r in (
        html_auth_router,
        html_account_router,
        html_admin_router,
        html_invites_router,
        html_password_router,
    ):
        app.include_router(r)
