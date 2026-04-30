from __future__ import annotations

import importlib
import os
import sys
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel


def _reload_app_with_env(*, base_path: str) -> FastAPI:
    """
    Load a fresh app instance after setting env vars that influence settings at import time.
    """
    os.environ["BASE_PATH"] = base_path
    os.environ.setdefault("JWT_SECRET", "test-secret")
    db_path = f"./test-{uuid.uuid4().hex}.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    # Ensure backend package root is importable so `import app...` works.
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # Reload settings + app so middleware picks up BASE_PATH.
    import app.core.config as config

    importlib.reload(config)

    # Reload modules that import `settings` at import time.
    import app.routes.invites as invites

    importlib.reload(invites)

    import app.main as main

    importlib.reload(main)
    # Ensure tables exist for tests that hit DB-backed routes.
    import app.db as db

    SQLModel.metadata.create_all(db.engine)
    return main.app


def test_root_redirect_includes_base_path() -> None:
    bp = "/s/e886e3c9ab5a7266e1f45/p/a5ca0047"
    app = _reload_app_with_env(base_path=bp)
    client = TestClient(app, base_url="http://testserver")

    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == f"{bp}/register"


def test_admin_redirect_includes_base_path() -> None:
    bp = "/s/e886e3c9ab5a7266e1f45/p/a5ca0047"
    app = _reload_app_with_env(base_path=bp)
    client = TestClient(app, base_url="http://testserver")

    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"{bp}/admin/login"


def test_html_links_and_form_actions_include_base_path() -> None:
    bp = "/s/e886e3c9ab5a7266e1f45/p/a5ca0047"
    app = _reload_app_with_env(base_path=bp)
    client = TestClient(app, base_url="http://testserver")

    # Base nav links
    r_login = client.get("/login")
    assert r_login.status_code == 200
    assert f'href="{bp}/register"' in r_login.text
    assert f'href="{bp}/login"' in r_login.text
    assert f'action="{bp}/login"' in r_login.text

    r_register = client.get("/register")
    assert r_register.status_code == 200
    assert f'action="{bp}/register"' in r_register.text

    # Admin login form action
    r_admin_login = client.get("/admin/login")
    assert r_admin_login.status_code == 200
    assert f'action="{bp}/admin/login"' in r_admin_login.text


def test_workbench_encoded_absolute_url_path_is_decoded_and_routed() -> None:
    bp = "/s/e886e3c9ab5a7266e1f45/p/a5ca0047"
    app = _reload_app_with_env(base_path=bp)
    client = TestClient(app, base_url="http://testserver")

    # Simulate Workbench sending an encoded absolute URL as the ASGI path.
    encoded = "/https%3A//workbench.socom.mil" + bp + "//admin"
    r = client.get(encoded, follow_redirects=False)
    # Should route to /admin, which redirects to /admin/login (with base_path prefix).
    assert r.status_code == 303
    assert r.headers["location"] == f"{bp}/admin/login"


def test_workbench_autodetects_prefix_when_base_path_unset() -> None:
    bp = "/s/e886e3c9ab5a7e147ea97/p/a693b2fa"
    # Unset BASE_PATH to exercise autodetection
    os.environ.pop("BASE_PATH", None)
    app = _reload_app_with_env(base_path="")
    client = TestClient(app, base_url="http://testserver")

    encoded = "/https%3A//workbench.socom.mil" + bp + "//docs"
    r = client.get(encoded)
    assert r.status_code == 200


def test_invite_url_uses_public_base_url_and_root_path() -> None:
    bp = "/s/e886e3c9ab5a7e147ea97/p/a693b2fa"
    os.environ["PUBLIC_BASE_URL"] = "https://workbench.socom.mil"
    os.environ["SEED_ADMIN_EMAIL"] = "admin@example.com"
    os.environ["SEED_ADMIN_PASSWORD"] = "admin123"
    app = _reload_app_with_env(base_path="")
    client = TestClient(app, base_url="http://testserver")

    # Create admin user via register (simplest) then login for token.
    client.post(
        "/register", data={"email": "admin@example.com", "password": "admin123"}
    )
    token = client.post(
        "/auth/token",
        data={"username": "admin@example.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ).json()["access_token"]

    # Simulate Workbench encoded path to /invites (so root_path is inferred).
    encoded_create = "/https%3A//workbench.socom.mil" + bp + "//invites"
    r = client.post(
        encoded_create,
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "new.user@example.com"},
    )
    assert r.status_code == 200
    invite_url = r.json()["invite_url"]
    assert invite_url.startswith(
        f"https://workbench.socom.mil{bp}/invites/accept?token="
    )
