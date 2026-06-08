from __future__ import annotations

import importlib
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location

import pytest
from starlette.requests import Request


@pytest.fixture(autouse=True)
def _isolated_app_config(monkeypatch, tmp_path):
    """Reload ``app.core.config`` and ``app.web.session`` without pollution from other API tests."""
    api_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

    for k in list(sys.modules.keys()):
        if k in ("app", "app.core.config", "app.web.session"):
            sys.modules.pop(k, None)

    app_pkg_dir = os.path.join(api_root, "app")
    spec = spec_from_file_location(
        "app",
        os.path.join(app_pkg_dir, "__init__.py"),
        submodule_search_locations=[app_pkg_dir],
    )
    assert spec and spec.loader
    app_pkg = module_from_spec(spec)
    sys.modules["app"] = app_pkg
    spec.loader.exec_module(app_pkg)

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cookie.db'}")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    import app.core.config as config_mod

    importlib.reload(config_mod)
    import app.web.session as session_mod

    importlib.reload(session_mod)
    yield config_mod, session_mod


def _request(https: bool = False) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/login",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8001),
        "scheme": "https" if https else "http",
        "root_path": "/s/svc/p/proj",
    }
    return Request(scope)


def test_local_mode_uses_base_path_and_infers_secure(
    monkeypatch, _isolated_app_config
) -> None:
    config_mod, session = _isolated_app_config
    monkeypatch.setattr(config_mod._defaults, "AUTH_COOKIE_DEPLOYMENT", "local")
    monkeypatch.setattr(config_mod._defaults, "AUTH_COOKIE_SECURE", None)
    config_mod.refresh_settings()
    importlib.reload(session)

    req_http = _request(https=False)
    assert session.auth_cookie_connect_mode() is False
    assert session.auth_cookie_secure(req_http) is False
    assert session.auth_cookie_path(req_http) == "/s/svc/p/proj"

    req_https = _request(https=True)
    assert session.auth_cookie_secure(req_https) is True


def test_connect_mode_forces_secure_and_root_path(
    monkeypatch, _isolated_app_config
) -> None:
    config_mod, session = _isolated_app_config
    monkeypatch.setattr(config_mod._defaults, "AUTH_COOKIE_DEPLOYMENT", "connect")
    config_mod.refresh_settings()
    importlib.reload(session)

    req = _request(https=False)
    assert session.auth_cookie_connect_mode() is True
    assert session.auth_cookie_secure(req) is True
    assert session.auth_cookie_path(req) == "/"
