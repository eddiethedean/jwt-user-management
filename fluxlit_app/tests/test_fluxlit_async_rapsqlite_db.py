from __future__ import annotations

import asyncio
import importlib
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location

from sqlmodel import SQLModel, select


def _reload_db_for_url(*, db_url: str):
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"

    SQLModel.metadata.clear()
    import sqlmodel.main as sqlmodel_main

    sqlmodel_main.default_registry.dispose()

    for k in list(sys.modules.keys()):
        if k == "app" or k.startswith("app."):
            sys.modules.pop(k, None)

    here = os.path.dirname(__file__)
    api_root = os.path.abspath(os.path.join(here, "..", "..", "user_management_api"))
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

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

    import app.db as db

    importlib.reload(db)
    return db


def test_async_engine_uses_rapsqlite_driver() -> None:
    db = _reload_db_for_url(db_url="sqlite:///:memory:")
    assert str(db.async_engine.url).startswith("sqlite+rapsqlite:")
    assert db.async_engine.url.drivername == "sqlite+rapsqlite"


def test_async_session_can_exec_select() -> None:
    db = _reload_db_for_url(db_url="sqlite:///:memory:")

    async def run() -> None:
        from app.models import User

        async with db.async_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        async with db.AsyncSessionLocal() as s:
            res = await s.exec(select(User).limit(1))
            _ = res.first()

    asyncio.run(run())
