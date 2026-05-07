from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from starlette.types import ASGIApp


def _load_wrapped_app(*, db_url: str) -> ASGIApp:
    """
    Reload backend modules that read settings at import time and return the ASGI app
    wrapped by the Workbench adapter (app.asgi:app).
    """
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ.pop("DIRECTORY_LOOKUP_URL", None)
    os.environ.pop("DIRECTORY_LOOKUP_TIMEOUT_S", None)
    os.environ.pop("DIRECTORY_LOOKUP_REQUIRED", None)

    # Avoid SQLAlchemy table redefinition issues across reloads.
    SQLModel.metadata.clear()
    import sqlmodel.main as sqlmodel_main

    sqlmodel_main.default_registry.dispose()

    # Streamlit tests (or other tools) can leave a non-package module named `app` in
    # sys.modules, which breaks our backend imports (`import app.core...`). Ensure
    # we start from a clean state.
    for k in list(sys.modules.keys()):
        if k == "app" or k.startswith("app."):
            sys.modules.pop(k, None)

    # Ensure the backend package root wins module resolution.
    here = os.path.dirname(__file__)
    api_root = os.path.abspath(os.path.join(here, ".."))
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

    # Streamlit (and AppTest) can create a non-package module named `app`. To make
    # backend imports robust, force-load the backend `app/` directory as the `app`
    # package explicitly.
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

    import app.core.security as security

    importlib.reload(security)

    import app.routes.admin as admin_routes

    importlib.reload(admin_routes)

    import app.main as main

    importlib.reload(main)

    import app.asgi as asgi

    importlib.reload(asgi)

    # Ensure schema exists.
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


def test_admin_redirects_use_relative_locations_under_workbench_prefix(
    tmp_path,
) -> None:
    prefix = "/s/e886e3c9ab5a7e147ea97/p/testproj"
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = _load_wrapped_app(db_url=db_url)

    # Seed admin user for login test.
    import app.db as db

    _seed_admin(db_engine=db.engine)

    client = TestClient(app, base_url="http://testserver", root_path=prefix)

    r = client.get(f"{prefix}/admin", follow_redirects=False)
    assert r.status_code == 303
    # Relative redirect is required to avoid Workbench rewriting to /proxy/<port>/...
    assert r.headers["location"].startswith("login?msg=")
    assert "next=%2Fadmin" in r.headers["location"] or "next=/admin" in r.headers["location"]

    r2 = client.post(
        f"{prefix}/login",
        data={"email": "admin@example.com", "password": "admin123"},
        follow_redirects=False,
    )
    assert r2.status_code == 303
    assert r2.headers["location"] in {"admin", "../admin"}
    assert "set-cookie" in {k.lower() for k in r2.headers.keys()}

    # Admin page should accept invite creation via form POST and render invite URL.
    r3 = client.post(
        f"{prefix}/admin/invite",
        data={"email": "new.user@example.com"},
        follow_redirects=False,
    )
    assert r3.status_code == 200
    assert "/invites/accept?token=" in r3.text

    # Ensure accept-form flow works even if DB returns naive datetimes (SQLite).
    # This is a regression test for Workbench where `expires_at` came back naive.
    import re

    m = re.search(r"invites/accept\?token=([^\s\"<]+)", r3.text)
    assert m
    invite_token = m.group(1)

    r_accept_get = client.get(f"{prefix}/invites/accept?token={invite_token}")
    assert r_accept_get.status_code == 200
    assert "new.user@example.com" in r_accept_get.text

    r4 = client.post(
        f"{prefix}/invites/accept-form",
        data={"token": invite_token, "password": "NewPassw0rd!123"},
        follow_redirects=False,
    )
    assert r4.status_code == 303
    loc2 = r4.headers["location"]
    assert loc2.startswith("http://") or loc2.startswith("https://")
    assert loc2.endswith(f"{prefix}/login")
