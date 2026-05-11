"""AppTest parity with ``streamlit_user/tests/test_user_app_apptest.py`` (FluxLit entry)."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

import fluxlit
from fluxlit.client import ApiClient

_REPO = Path(__file__).resolve().parents[2]
_UM = _REPO / "user_management_api"
_FLUX = _REPO / "fluxlit_app"
_FLUXLIT_MAIN = Path(fluxlit.__file__).resolve().parent / "streamlit" / "main.py"


@pytest.fixture(autouse=True)
def _paths_and_env(tmp_path, monkeypatch):
    for p in (str(_FLUX), str(_UM)):
        if p not in sys.path:
            sys.path.insert(0, p)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/st.db")
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


class _Resp:
    def __init__(self, ok=True, status_code=200, json_data=None, text=""):
        self.ok = ok
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data


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


def _patch_api_client(monkeypatch, fake_request):
    monkeypatch.setattr(ApiClient, "request", fake_request)


def test_login_success_sets_session(monkeypatch):
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

    _patch_api_client(monkeypatch, fake_request)

    monkeypatch.setenv("FLUXLIT_APP", "main:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://testserver/api")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception

    _text_input_by_key(at, "login_email").input("user@test.local")
    _text_input_by_key(at, "login_password").input("pw")
    _click_button(at, "Sign in")
    at.run()
    assert not at.exception

    assert "access_token" in at.session_state
    assert at.session_state["access_token"] == "tok"
    assert any("signed in" in s.value.lower() for s in at.success)
    assert any("(US)" in c.value for c in at.caption)


def test_forgot_password_shows_non_enumerating_message(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "POST" and "/password/forgot" in p:
            assert kwargs.get("json") == {"email": "user@test.local"}
            return httpx.Response(200, json={"ok": True})
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)

    monkeypatch.setenv("FLUXLIT_APP", "main:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://testserver/api")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception

    _set_public_page(at, "Reset password")
    at.run()
    assert not at.exception

    _text_input_by_key(at, "forgot_email").input("user@test.local")
    _click_button(at, "Send reset link")
    at.run()
    assert not at.exception

    assert any("reset email has been sent" in s.value.lower() for s in at.success)


def test_sign_out_clears_session_state(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(
                200, json={"access_token": "tok", "token_type": "bearer"}
            )
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)

    monkeypatch.setenv("FLUXLIT_APP", "main:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://testserver/api")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30)
    at.run()
    assert not at.exception

    _text_input_by_key(at, "login_email").input("user@test.local")
    _text_input_by_key(at, "login_password").input("pw")
    _click_button(at, "Sign in")
    at.run()
    assert not at.exception
    assert "access_token" in at.session_state
    assert at.session_state["access_token"] == "tok"

    _click_button(at, "Sign out")
    at.run()
    assert not at.exception
    assert (
        "access_token" not in at.session_state
        or at.session_state.get("access_token") in (None, "")
    )


def test_login_backend_request_exception_is_shown(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            raise httpx.TimeoutException("nope")
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)

    monkeypatch.setenv("FLUXLIT_APP", "main:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://testserver/api")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")

    at = AppTest.from_file(str(_FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception

    _text_input_by_key(at, "login_email").input("user@test.local")
    _text_input_by_key(at, "login_password").input("pw")
    _click_button(at, "Sign in")
    at.run()
    assert not at.exception

    assert len(at.error) >= 1
    assert "Backend request failed" in at.error[0].value
