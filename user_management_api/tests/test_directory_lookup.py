from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from starlette.types import ASGIApp


def _load_wrapped_app(*, db_url: str) -> ASGIApp:
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["DIRECTORY_LOOKUP_URL"] = "http://directory.test/ldapEmail"
    os.environ["DIRECTORY_LOOKUP_REQUIRED"] = "true"

    SQLModel.metadata.clear()
    import sqlmodel.main as sqlmodel_main

    sqlmodel_main.default_registry.dispose()

    for k in list(sys.modules.keys()):
        if k == "app" or k.startswith("app."):
            sys.modules.pop(k, None)

    here = os.path.dirname(__file__)
    api_root = os.path.abspath(os.path.join(here, ".."))
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

    import app.services.directory as directory

    importlib.reload(directory)

    import app.routes.auth as auth_routes

    importlib.reload(auth_routes)

    import app.routes.admin as admin_routes

    importlib.reload(admin_routes)

    import app.main as main

    importlib.reload(main)

    import app.asgi as asgi

    importlib.reload(asgi)

    SQLModel.metadata.create_all(db.engine)
    return asgi.app  # type: ignore[return-value]


def _seed_admin(*, db_engine) -> None:
    from app.core.security import hash_password
    from app.models import User

    with Session(db_engine) as s:
        s.add(
            User(
                email="admin@example.com",
                hashed_password=hash_password("admin123"),
                is_admin=True,
                created_at=datetime.now(timezone.utc),
            )
        )
        s.commit()


class _Resp:
    def __init__(self, *, status_code: int, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        return self._json_data


def test_register_rejects_email_not_in_directory(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    # Directory returns 404 (not found)
    import app.services.directory as directory

    monkeypatch.setattr(directory.httpx, "get", lambda *a, **k: _Resp(status_code=404))

    client = TestClient(app, base_url="http://testserver")
    r = client.post(
        "/register", data={"email": "nobody@example.com"}, follow_redirects=False
    )
    assert r.status_code == 400
    assert "Email not found in directory" in r.text


def test_lookup_parses_country_from_directory_response(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _ = _load_wrapped_app(db_url=db_url)

    # Directory returns record with "co": ["US"].
    import app.services.directory as directory

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={"attributes": {"mail": ["user@example.com"], "co": ["US"]}},
        ),
    )

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.country == "US"


def test_lookup_strips_c_prefix_from_country(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _ = _load_wrapped_app(db_url=db_url)

    import app.services.directory as directory

    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(
            status_code=200,
            json_data={"attributes": {"mail": ["user@example.com"], "c": ["C=US"]}},
        ),
    )

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.country == "US"


def test_lookup_accepts_json_string_payload(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    _ = _load_wrapped_app(db_url=db_url)

    import app.services.directory as directory

    payload = {
        "attributes": {
            "mail": ["user@example.com"],
            "co": ["US"],
            "displayName": ["X"],
        },
        "dn": "CN=X",
    }
    monkeypatch.setattr(
        directory.httpx,
        "get",
        lambda *a, **k: _Resp(status_code=200, json_data=json.dumps(payload)),
    )

    rec = directory.lookup_email("user@example.com")
    assert rec
    assert rec.email == "user@example.com"
    assert rec.country == "US"


def test_admin_invite_rejects_email_not_in_directory(tmp_path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    import app.db as db

    _seed_admin(db_engine=db.engine)

    import app.services.directory as directory

    monkeypatch.setattr(directory.httpx, "get", lambda *a, **k: _Resp(status_code=404))

    client = TestClient(app, base_url="http://testserver")
    r_login = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r_login.status_code == 303

    r = client.post(
        "/admin/invite", data={"email": "nobody@example.com"}, follow_redirects=False
    )
    assert r.status_code == 400
    assert "Email not found in directory" in r.text
