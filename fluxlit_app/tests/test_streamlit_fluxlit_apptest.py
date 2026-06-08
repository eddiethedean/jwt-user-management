"""Streamlit AppTest coverage for the FluxLit user management page."""

from __future__ import annotations

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from fluxlit.client import ApiClient
from streamlit_apptest_helpers import (
    FLUXLIT_MAIN,
    click_button,
    fluxlit_env,
    setup_streamlit_paths_and_env,
    text_input_by_key,
)


@pytest.fixture(autouse=True)
def _paths_and_env(tmp_path, monkeypatch):
    setup_streamlit_paths_and_env(tmp_path, monkeypatch)
    yield


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
    fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception

    text_input_by_key(at, "login_email").input("user@test.local")
    text_input_by_key(at, "login_password").input("pw")
    click_button(at, label="Sign in")
    at.run()
    assert not at.exception

    assert at.session_state["access_token"] == "tok"
    assert at.session_state["user_auth"].is_authenticated
    assert any("signed in" in s.value.lower() for s in at.success)
    assert at.session_state["_page"] == "Account"
    assert at.session_state["_me"]["country"] == "US"


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
    fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception

    text_input_by_key(at, "login_reset_email").input("user@test.local")
    click_button(at, key="login_send_reset")
    at.run()
    assert not at.exception

    assert any("reset email has been sent" in s.value.lower() for s in at.success)


def test_login_backend_request_exception_is_shown(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            raise httpx.TimeoutException("nope")
        return httpx.Response(200, json={})

    _patch_api_client(monkeypatch, fake_request)
    fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception

    text_input_by_key(at, "login_email").input("user@test.local")
    text_input_by_key(at, "login_password").input("pw")
    click_button(at, label="Sign in")
    at.run()
    assert not at.exception

    assert len(at.error) == 1
    assert "Backend request failed" in at.error[0].value
