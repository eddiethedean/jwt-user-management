"""Additional Streamlit AppTests for the FluxLit user management page."""

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


def test_login_invalid_credentials_shows_error(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        if method == "POST" and "/auth/token" in p:
            return httpx.Response(400, json={"detail": "Incorrect email or password"})
        return httpx.Response(200, json={})

    monkeypatch.setattr(ApiClient, "request", fake_request)
    fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception

    text_input_by_key(at, "login_email").input("bad@test.local")
    text_input_by_key(at, "login_password").input("wrong")
    click_button(at, label="Sign in")
    at.run()
    assert not at.exception

    assert "access_token" not in at.session_state
    assert len(at.error) == 1
    assert (
        at.error[0].value
        == "Invalid email or password: 400 (Incorrect email or password)"
    )


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
    fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(FLUXLIT_MAIN), default_timeout=30)
    at.run()
    assert not at.exception
    text_input_by_key(at, "login_email").input("user@test.local")
    text_input_by_key(at, "login_password").input("pw")
    click_button(at, label="Sign in")
    at.run()
    assert not at.exception
    assert at.session_state["access_token"] == "tok"
    assert at.session_state["username"] == "user@test.local"

    click_button(at, key="sign_out_sidebar")
    at.run()
    assert not at.exception
    assert "access_token" not in at.session_state
    assert "username" not in at.session_state
    assert "_me" not in at.session_state
    assert not at.session_state["user_auth"].is_authenticated


def test_forgot_password_shows_error_when_backend_fails(monkeypatch):
    def fake_request(self, method: str, path: str, **kwargs):
        p = path if path.startswith("/") else f"/{path}"
        if method == "POST" and "/password/forgot" in p:
            return httpx.Response(503, text="down")
        if method == "GET" and "/__meta" in p:
            return httpx.Response(200, json={"ok": True, "external_api_base": ""})
        return httpx.Response(200, json={})

    monkeypatch.setattr(ApiClient, "request", fake_request)
    fluxlit_env(monkeypatch)

    at = AppTest.from_file(str(FLUXLIT_MAIN), default_timeout=30).run()
    assert not at.exception
    text_input_by_key(at, "login_reset_email").input("x@test.local")
    click_button(at, key="login_send_reset")
    at.run()
    assert not at.exception

    assert len(at.error) == 1
    assert "503" in at.error[0].value or "failed" in at.error[0].value.lower()
