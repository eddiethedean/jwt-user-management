import os

import pytest
import httpx
from streamlit.testing.v1 import AppTest

from app_paths import USER_APP_PY


@pytest.fixture(autouse=True)
def _env():
    os.environ["BACKEND_URL"] = "http://testserver"
    yield


class _Resp:
    def __init__(self, ok=True, status_code=200, json_data=None, text=""):
        self.ok = ok
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data


def _input_text(at: AppTest, label: str, value: str, key_contains: str) -> None:
    matches = [t for t in at.text_input if getattr(t, "label", None) == label]
    matches = [t for t in matches if key_contains in (getattr(t, "key", "") or "")]
    if not matches:
        raise AssertionError(f"Text input not found: {label!r} ({key_contains=})")
    matches[0].input(value)


def _click_button(at: AppTest, label: str) -> None:
    for b in at.button:
        if getattr(b, "label", None) == label or getattr(b, "value", None) == label:
            b.click()
            return
    raise AssertionError(f"Button not found: {label}")


def test_login_invalid_credentials_shows_error(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/auth/token"):
            return _Resp(ok=False, status_code=401, json_data={"detail": "Invalid"})
        return _Resp(ok=True, json_data={})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(USER_APP_PY, default_timeout=30).run()
    assert not at.exception

    _input_text(at, "Email", "bad@test.local", "login_email")
    _input_text(at, "Password", "wrong", "login_password")
    _click_button(at, "Sign in")
    at.run()

    assert "access_token" not in at.session_state
    assert len(at.error) >= 1


def test_sign_out_clears_username_and_token(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/auth/token"):
            return _Resp(
                ok=True, json_data={"access_token": "tok", "token_type": "bearer"}
            )
        return _Resp(ok=True, json_data={})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _Resp(ok=True, json_data={"country": "US"})
    )

    at = AppTest.from_file(USER_APP_PY, default_timeout=30)
    at.run()
    _input_text(at, "Email", "user@test.local", "login_email")
    _input_text(at, "Password", "pw", "login_password")
    _click_button(at, "Sign in")
    at.run()
    assert at.session_state["access_token"] == "tok"
    assert at.session_state["username"] == "user@test.local"

    _click_button(at, "Sign out")
    at.run()
    assert "access_token" not in at.session_state
    assert "username" not in at.session_state
    assert "_me" not in at.session_state


def test_forgot_password_shows_error_when_backend_fails(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/password/forgot"):
            return _Resp(ok=False, status_code=503, text="down")
        return _Resp(ok=True, json_data={})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(USER_APP_PY, default_timeout=30).run()
    _input_text(at, "Email", "x@test.local", "forgot_email")
    _click_button(at, "Send reset link")
    at.run()

    assert len(at.error) >= 1
    assert "503" in at.error[0].value or "failed" in at.error[0].value.lower()
