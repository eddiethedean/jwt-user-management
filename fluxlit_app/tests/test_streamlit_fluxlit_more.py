"""Additional Streamlit AppTests for the FluxLit user management page."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

import fluxlit
from fluxlit.client import ApiClient

_REPO = Path(__file__).resolve().parents[2]
_FLUX = _REPO / "fluxlit_app"
_FLUXLIT_MAIN = Path(fluxlit.__file__).resolve().parent / "streamlit" / "main.py"


@pytest.fixture(autouse=True)
def _paths_and_env(tmp_path, monkeypatch):
    for p in (str(_FLUX),):
        if p not in sys.path:
            sys.path.insert(0, p)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/st2.db")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    for k in ("DIRECTORY_LOOKUP_URL", "DIRECTORY_LOOKUP_REQUIRED"):
        monkeypatch.delenv(k, raising=False)
    for mod in (
        "main",
        "fluxlit_gateway",
        "api_backend",
        "paths",
        "streamlit_ui",
        "auth_state",
        "ui_helpers",
    ):
        sys.modules.pop(mod, None)
    for k in list(sys.modules.keys()):
        if k == "ui" or k.startswith("ui."):
            sys.modules.pop(k, None)
    yield


def _text_input_by_key(at: AppTest, key: str):
    matches = [t for t in at.text_input if getattr(t, "key", None) == key]
    if not matches:
        raise AssertionError(f"Text input not found for key={key!r}")
    return matches[0]


def _click_button(at: AppTest, label: str) -> None:
    for b in at.button:
        if getattr(b, "label", None) == label or getattr(b, "value", None) == label:
            b.click()
            return
    raise AssertionError(f"Button not found: {label}")


def _set_public_page(at: AppTest, page: str) -> None:
    matches = [r for r in at.radio if getattr(r, "label", None) == "Go to"]
    if not matches:
        raise AssertionError("Public navigation radio not found")
    matches[0].set_value(page)


def _fluxlit_env(monkeypatch):
    monkeypatch.setenv("FLUXLIT_APP", "main:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://testserver/api")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")


def test_login_invalid_credentials_shows_error(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(401, json={"detail": "Invalid"})
        return httpx.Response(200, json={})

    monkeypatch.setattr(ApiClient, "request", fake_request)
    _fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception

    _text_input_by_key(at, "login_email").input("bad@test.local")
    _text_input_by_key(at, "login_password").input("wrong")
    _click_button(at, "Sign in")
    at.run()
    assert not at.exception

    assert "access_token" not in at.session_state
    assert len(at.error) >= 1


def test_sign_out_clears_username_and_token(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        if method == "GET" and "/users/me" in p:
            return httpx.Response(200, json={"country": "US"})
        return httpx.Response(200, json={})

    monkeypatch.setattr(ApiClient, "request", fake_request)
    _fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30)
    at.run()
    assert not at.exception
    _text_input_by_key(at, "login_email").input("user@test.local")
    _text_input_by_key(at, "login_password").input("pw")
    _click_button(at, "Sign in")
    at.run()
    assert not at.exception
    assert at.session_state["access_token"] == "tok"
    assert at.session_state["username"] == "user@test.local"

    _click_button(at, "Sign out")
    at.run()
    assert not at.exception
    assert "access_token" not in at.session_state
    assert "username" not in at.session_state
    assert "_me" not in at.session_state


def test_forgot_password_shows_error_when_backend_fails(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "POST" and "/password/forgot" in p:
            return httpx.Response(503, text="down")
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    monkeypatch.setattr(ApiClient, "request", fake_request)
    _fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception
    _set_public_page(at, "Reset password")
    at.run()
    assert not at.exception
    _text_input_by_key(at, "forgot_email").input("x@test.local")
    _click_button(at, "Send reset link")
    at.run()
    assert not at.exception

    assert len(at.error) >= 1
    assert "503" in at.error[0].value or "failed" in at.error[0].value.lower()
