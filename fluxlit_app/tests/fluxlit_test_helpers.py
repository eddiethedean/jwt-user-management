"""Helpers to load ``fluxlit_app.main:app`` for integration tests."""

from __future__ import annotations

import importlib
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

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
    """Return the FluxLit instance with DB at ``db_url``."""
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
    os.environ["JWT_SECRET"] = "test-secret-for-jwt-signing"
    os.environ["JWT_ALLOW_WEAK_SECRET"] = "1"
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

    for mod_name in (
        "app.invite_email_domains",
        "app.db",
        "app.core.security",
        "app.services.email",
        "app.routes.admin",
        "app.routes.public_urls",
        "app.routes.invites",
        "app.routes.password_reset",
        "app.routes.users",
        "app.routes.auth",
    ):
        importlib.reload(importlib.import_module(mod_name))

    import app.models  # noqa: F401

    flux = importlib.import_module("main")

    if public_base_url is not None:
        os.environ.pop("FLUXLIT_PUBLIC_BASE_URL", None)
        os.environ.pop("PUBLIC_BASE_URL", None)

    import app.db as db

    SQLModel.metadata.create_all(db.engine)
    return flux.app
