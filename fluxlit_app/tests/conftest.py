"""
Shared helpers to load ``fluxlit_app.main:app`` with a fresh ``app`` package
and SQLite DB.
"""

from __future__ import annotations

# Avoid loading ``fluxlit_app/.env`` during pytest (would leak PUBLIC_BASE_URL, etc.).
import os

os.environ.setdefault("FLUXLIT_TESTS", "1")

import importlib
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import SQLModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FLUX_ROOT = _REPO_ROOT / "fluxlit_app"

_DEFAULT_TEST_INVITE_DOMAINS: tuple[str, ...] = (
    "example.com",
    "example.org",
    "test.local",
    "allowed.org",
    "corp.com",
    "socom.mil",
    "soc.mil",
    "b.c",
)


def _apply_pytest_backend_defaults(
    config_mod: Any,
    *,
    invite_allowed_email_domains: tuple[str, ...] | None,
    public_base_url: str | None = None,
) -> None:
    if invite_allowed_email_domains is not None:
        config_mod._defaults.INVITE_ALLOWED_EMAIL_DOMAINS = invite_allowed_email_domains
    else:
        config_mod._defaults.INVITE_ALLOWED_EMAIL_DOMAINS = _DEFAULT_TEST_INVITE_DOMAINS
    if public_base_url is not None:
        config_mod._defaults.PUBLIC_BASE_URL = public_base_url
    config_mod.refresh_settings()


def purge_other_repo_app_packages(*, repo_root: Path, fluxlit_app_root: Path) -> None:
    """Remove sibling repo dirs that expose a top-level ``app`` (except ``fluxlit_app``)."""
    flux = fluxlit_app_root.resolve()
    for child in repo_root.iterdir():
        if not child.is_dir() or child.resolve() == flux:
            continue
        if not (child / "app" / "__init__.py").is_file():
            continue
        p = str(child.resolve())
        while p in sys.path:
            sys.path.remove(p)


def _ensure_sys_path() -> None:
    flux = str(_FLUX_ROOT)
    if flux not in sys.path:
        sys.path.insert(0, flux)


@pytest.fixture(autouse=True)
def _fluxlit_tests_restore_sys_path() -> Any:
    """Other repo trees also ship a top-level ``app``; prefer ours only for these tests."""
    saved = list(sys.path)
    purge_other_repo_app_packages(repo_root=_REPO_ROOT, fluxlit_app_root=_FLUX_ROOT)
    _ensure_sys_path()
    yield
    sys.path[:] = saved


def _purge_reloadable_modules() -> None:
    for k in list(sys.modules.keys()):
        if k in (
            "main",
            "fluxlit_gateway",
            "api_backend",
            "paths",
            "streamlit_ui",
            "auth_state",
            "ui_helpers",
        ):
            sys.modules.pop(k, None)
        elif k == "ui" or k.startswith("ui."):
            sys.modules.pop(k, None)
        elif k == "app" or k.startswith("app."):
            sys.modules.pop(k, None)


def _load_app_package() -> None:
    _ensure_sys_path()
    app_pkg_dir = _FLUX_ROOT / "app"
    app_init = app_pkg_dir / "__init__.py"
    spec = spec_from_file_location(
        "app", str(app_init), submodule_search_locations=[str(app_pkg_dir)]
    )
    assert spec and spec.loader
    app_pkg = module_from_spec(spec)
    sys.modules["app"] = app_pkg
    spec.loader.exec_module(app_pkg)


def load_fluxlit_app(
    *,
    db_url: str,
    extra_env: dict[str, str] | None = None,
    invite_allowed_email_domains: tuple[str, ...] | None = None,
    public_base_url: str | None = None,
) -> Any:
    """
    Return the :class:`fluxlit.app.FluxLit` instance with DB at ``db_url``.
    Use :class:`fluxlit.testing.FluxLitTestClient` and ``/api/...`` paths in tests.
    """
    for k in (
        "DIRECTORY_LOOKUP_URL",
        "DIRECTORY_LOOKUP_REQUIRED",
        "DIRECTORY_LOOKUP_VERIFY_SSL",
    ):
        os.environ.pop(k, None)

    for k in list(os.environ):
        if k.startswith("FLUXLIT_"):
            os.environ.pop(k, None)

    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"
    if extra_env:
        os.environ.update(extra_env)

    SQLModel.metadata.clear()
    import sqlmodel.main as sqlmodel_main

    sqlmodel_main.default_registry.dispose()

    _purge_reloadable_modules()
    _load_app_package()

    import app.core.config as config

    importlib.reload(config)
    _apply_pytest_backend_defaults(
        config,
        invite_allowed_email_domains=invite_allowed_email_domains,
        public_base_url=public_base_url,
    )

    import app.invite_email_domains as invite_email_domains_mod

    importlib.reload(invite_email_domains_mod)

    import app.db as db

    importlib.reload(db)

    import app.core.security as security

    importlib.reload(security)

    import app.services.email as email_service

    importlib.reload(email_service)

    import app.routes.admin as admin_routes

    importlib.reload(admin_routes)

    import app.routes.public_urls as public_urls_routes

    importlib.reload(public_urls_routes)

    import app.routes.invites as invites_routes

    importlib.reload(invites_routes)

    import app.routes.password_reset as password_reset_routes

    importlib.reload(password_reset_routes)

    import app.routes.users as users_routes

    importlib.reload(users_routes)

    import app.routes.auth as auth_routes

    importlib.reload(auth_routes)

    import app.models  # noqa: F401 — register models on metadata

    flux = importlib.import_module("main")

    if public_base_url is not None:
        os.environ.pop("FLUXLIT_PUBLIC_BASE_URL", None)
        os.environ.pop("PUBLIC_BASE_URL", None)

    SQLModel.metadata.create_all(db.engine)
    return flux.app
