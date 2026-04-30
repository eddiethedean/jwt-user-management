from __future__ import annotations

import importlib
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _reload_app_with_env(*, base_path: str) -> FastAPI:
    """
    Load a fresh app instance after setting env vars that influence settings at import time.
    """
    os.environ["BASE_PATH"] = base_path
    os.environ.setdefault("JWT_SECRET", "test-secret")

    # Ensure backend package root is importable so `import app...` works.
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # Reload settings + app so middleware picks up BASE_PATH.
    import app.core.config as config

    importlib.reload(config)

    import app.main as main

    importlib.reload(main)
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
