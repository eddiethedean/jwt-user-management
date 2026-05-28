from __future__ import annotations

import importlib

from starlette.requests import Request

import app.core.config as config_mod
from app.web import session


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


def test_local_mode_uses_base_path_and_infers_secure(monkeypatch) -> None:
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


def test_connect_mode_forces_secure_and_root_path(monkeypatch) -> None:
    monkeypatch.setattr(config_mod._defaults, "AUTH_COOKIE_DEPLOYMENT", "connect")
    config_mod.refresh_settings()
    importlib.reload(session)

    req = _request(https=False)
    assert session.auth_cookie_connect_mode() is True
    assert session.auth_cookie_secure(req) is True
    assert session.auth_cookie_path(req) == "/"
