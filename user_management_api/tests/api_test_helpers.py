"""
Shared helpers for user_management_api integration tests.

Kept separate from ``conftest.py`` so explicit imports do not collide with other
packages' ``conftest`` modules when pytest loads multiple ``testpaths``.
"""

from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from starlette.types import ASGIApp

DEFAULT_TEST_INVITE_DOMAINS: tuple[str, ...] = (
    "example.com",
    "example.org",
    "test.local",
    "allowed.org",
    "corp.com",
    "socom.mil",
    "soc.mil",
    "b.c",
)


class FakeHttpxResponse:
    """Minimal httpx response stub for directory service mocks."""

    def __init__(self, *, status_code: int, json_data: Any = None):
        self.status_code = status_code
        self._json_data = json_data

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        return self._json_data


def _apply_test_invite_config(
    config_mod: Any,
    *,
    invite_allowed_email_domains: tuple[str, ...] | None,
) -> None:
    if invite_allowed_email_domains is not None:
        config_mod._defaults.INVITE_ALLOWED_EMAIL_DOMAINS = invite_allowed_email_domains
    else:
        config_mod._defaults.INVITE_ALLOWED_EMAIL_DOMAINS = DEFAULT_TEST_INVITE_DOMAINS
    config_mod.refresh_settings()


def _ensure_api_root_on_path() -> str:
    here = os.path.dirname(__file__)
    api_root = os.path.abspath(os.path.join(here, ".."))
    if api_root not in sys.path:
        sys.path.insert(0, api_root)
    return api_root


def _clear_app_modules() -> None:
    for k in list(sys.modules.keys()):
        if k == "app" or k.startswith("app."):
            sys.modules.pop(k, None)


def load_wrapped_app(
    *,
    db_url: str,
    enable_directory: bool = False,
    invite_allowed_email_domains: tuple[str, ...] | None = None,
) -> ASGIApp:
    """Load the backend ASGI app (app.asgi:app) with a fresh SQLite DB and settings."""
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret-for-jwt-signing"
    os.environ["JWT_ALLOW_WEAK_SECRET"] = "1"
    if enable_directory:
        os.environ["DIRECTORY_LOOKUP_URL"] = "http://directory.test/ldapEmail"
        os.environ["DIRECTORY_LOOKUP_REQUIRED"] = "true"
    else:
        os.environ.pop("DIRECTORY_LOOKUP_URL", None)
        os.environ.pop("DIRECTORY_LOOKUP_REQUIRED", None)

    SQLModel.metadata.clear()
    import sqlmodel.main as sqlmodel_main

    sqlmodel_main.default_registry.dispose()
    _clear_app_modules()
    _ensure_api_root_on_path()

    api_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app_pkg_dir = os.path.join(api_root, "app")
    app_init = os.path.join(app_pkg_dir, "__init__.py")
    spec = spec_from_file_location(
        "app", app_init, submodule_search_locations=[app_pkg_dir]
    )
    assert spec and spec.loader
    app_pkg = module_from_spec(spec)
    sys.modules["app"] = app_pkg
    spec.loader.exec_module(app_pkg)

    import app.core.config as config

    importlib.reload(config)
    _apply_test_invite_config(
        config, invite_allowed_email_domains=invite_allowed_email_domains
    )

    for mod_name in (
        "app.invite_email_domains",
        "app.db",
        "app.core.security",
        "app.routes.deps",
        "app.routes.email_links",
        "app.services.directory",
        "app.services.email",
        "app.services.tokens",
        "app.routes.auth",
        "app.routes.invites",
        "app.routes.admin",
        "app.routes.users",
        "app.routes.password_reset",
        "app.routes.account",
        "app.core.email_validation",
        "app.core.rate_limit",
        "app.web.csrf",
        "app.schemas.admin",
        "app.main",
        "app.asgi",
    ):
        importlib.reload(importlib.import_module(mod_name))

    import app.db as db

    SQLModel.metadata.create_all(db.engine)
    return importlib.import_module("app.asgi").app  # type: ignore[return-value]


def seed_user(
    *,
    db_engine: Any,
    email: str,
    password: str,
    is_admin: bool = False,
    is_active: bool = True,
) -> int:
    from app.core.security import hash_password
    from app.models import User

    with Session(db_engine) as s:
        u = User(
            email=email,
            hashed_password=hash_password(password),
            is_admin=is_admin,
            is_active=is_active,
            created_at=datetime.now(timezone.utc),
        )
        s.add(u)
        s.commit()
        s.refresh(u)
        assert u.id is not None
        return int(u.id)


def seed_admin(*, db_engine: Any) -> int:
    return seed_user(
        db_engine=db_engine,
        email="admin@example.com",
        password="admin123",
        is_admin=True,
    )


def seed_unused_invite(
    *,
    db_engine: Any,
    email: str,
    grant_admin: bool = False,
) -> str:
    from app.models import InviteToken

    raw = InviteToken.new_raw_token()
    now = datetime.now(timezone.utc)
    inv = InviteToken(
        email=email,
        token_hash=InviteToken.hash_token(raw),
        created_at=now,
        expires_at=now.replace(year=2099),
        used_at=None,
        grant_admin=grant_admin,
    )
    with Session(db_engine) as s:
        s.add(inv)
        s.commit()
    return raw


def bearer_for(client: TestClient, *, email: str, password: str) -> dict[str, str]:
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
