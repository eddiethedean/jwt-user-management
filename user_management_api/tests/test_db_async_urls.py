from __future__ import annotations

import importlib
import os
import ssl
import sys
from typing import Protocol, cast


class _DbModule(Protocol):
    def _async_db_url(self, url: str) -> str: ...

    def _clean_async_postgres_url(self, url: str) -> str: ...

    def _async_connect_args(self, url: str) -> dict[str, object]: ...


def _import_db_module(db_url: str, monkeypatch) -> _DbModule:
    """Import ``app.db`` without requiring a live Postgres driver."""
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"
    monkeypatch.setattr("sqlmodel.create_engine", lambda *a, **k: object())
    monkeypatch.setattr(
        "sqlalchemy.ext.asyncio.create_async_engine", lambda *a, **k: object()
    )
    for key in list(sys.modules.keys()):
        if key == "app.core.config" or key == "app.db":
            sys.modules.pop(key, None)
    import app.core.config as config_mod

    importlib.reload(config_mod)
    import app.db as db_mod

    importlib.reload(db_mod)
    return cast(_DbModule, db_mod)


def test_async_db_url_uses_aiosqlite_for_sqlite(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 't.db'}"
    db_mod = _import_db_module(db_url, monkeypatch)
    assert db_mod._async_db_url(db_url).startswith("sqlite+aiosqlite:///")


def test_async_db_url_migrates_legacy_rapsqlite_url(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite+rapsqlite:///{tmp_path / 't.db'}"
    db_mod = _import_db_module("sqlite:///ignored.db", monkeypatch)
    assert db_mod._async_db_url(db_url).startswith("sqlite+aiosqlite:///")


def test_async_db_url_uses_asyncpg_for_postgres_when_enabled(monkeypatch) -> None:
    url = "postgresql://user:pass@localhost:5432/app"
    db_mod = _import_db_module(url, monkeypatch)
    assert (
        db_mod._async_db_url(url) == "postgresql+asyncpg://user:pass@localhost:5432/app"
    )


def test_async_db_url_raises_when_postgres_disabled(monkeypatch) -> None:
    url = "postgresql://user:pass@localhost:5432/app"
    db_mod = _import_db_module(url, monkeypatch)
    import app.core.config as config_mod
    import pytest

    monkeypatch.setattr(config_mod._defaults, "POSTGRES_ASYNC_ENABLED", False)
    config_mod.refresh_settings()
    with pytest.raises(RuntimeError, match="POSTGRES_ASYNC_ENABLED"):
        db_mod._async_db_url(url)


def test_clean_async_postgres_url_strips_sslmode(monkeypatch) -> None:
    db_mod = _import_db_module("postgresql://localhost/db?sslmode=require", monkeypatch)
    assert (
        db_mod._clean_async_postgres_url(
            "postgresql+asyncpg://localhost/db?sslmode=require"
        )
        == "postgresql+asyncpg://localhost/db"
    )


def test_async_connect_args_adds_relaxed_ssl_context(monkeypatch) -> None:
    url = "postgresql://localhost/db?sslmode=require"
    db_mod = _import_db_module(url, monkeypatch)
    args = db_mod._async_connect_args(url)
    assert "ssl" in args
    assert isinstance(args["ssl"], ssl.SSLContext)
    assert args["ssl"].verify_mode == ssl.CERT_NONE


def test_async_connect_args_empty_for_sqlite(tmp_path, monkeypatch) -> None:
    url = f"sqlite:///{tmp_path / 't.db'}"
    db_mod = _import_db_module(url, monkeypatch)
    assert db_mod._async_connect_args(url) == {}
