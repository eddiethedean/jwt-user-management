"""
Shared helpers to load ``fluxlit_app.fluxlit_gateway:app`` with a fresh
``user_management_api`` ``app`` package and SQLite DB (same strategy as
``user_management_api/tests``).
"""

from __future__ import annotations

import importlib
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

from sqlmodel import SQLModel

# ``fluxlit_app/tests/conftest.py`` → repo root is ``parents[2]``.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_UM_ROOT = _REPO_ROOT / "user_management_api"
_FLUX_ROOT = _REPO_ROOT / "fluxlit_app"


def _ensure_sys_path() -> None:
    # FluxLit app dir first so ``import ui`` resolves to this project (not ``app``).
    for p in (str(_FLUX_ROOT), str(_UM_ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)


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
    app_pkg_dir = _UM_ROOT / "app"
    app_init = app_pkg_dir / "__init__.py"
    spec = spec_from_file_location(
        "app", str(app_init), submodule_search_locations=[str(app_pkg_dir)]
    )
    assert spec and spec.loader
    app_pkg = module_from_spec(spec)
    sys.modules["app"] = app_pkg
    spec.loader.exec_module(app_pkg)


def load_fluxlit_app(*, db_url: str, extra_env: dict[str, str] | None = None) -> Any:
    """
    Return the :class:`fluxlit.app.FluxLit` instance with DB at ``db_url``.
    Use :class:`fluxlit.testing.FluxLitTestClient` and ``/api/...`` paths in tests.
    """
    for k in (
        "DIRECTORY_LOOKUP_URL",
        "DIRECTORY_LOOKUP_REQUIRED",
        "DIRECTORY_LOOKUP_TIMEOUT_S",
        "DIRECTORY_LOOKUP_VERIFY_SSL",
    ):
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

    import app.db as db

    importlib.reload(db)

    import app.core.security as security

    importlib.reload(security)

    import app.services.email as email_service

    importlib.reload(email_service)

    import app.routes.admin as admin_routes

    importlib.reload(admin_routes)

    import app.routes.invites as invites_routes

    importlib.reload(invites_routes)

    import app.routes.password_reset as password_reset_routes

    importlib.reload(password_reset_routes)

    import app.routes.users as users_routes

    importlib.reload(users_routes)

    import app.routes.auth as auth_routes

    importlib.reload(auth_routes)

    import app.models  # noqa: F401 — register models on metadata

    flux = importlib.import_module("fluxlit_gateway")

    SQLModel.metadata.create_all(db.engine)
    return flux.app
