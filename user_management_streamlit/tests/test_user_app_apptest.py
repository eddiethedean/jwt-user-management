import os
import pytest
import httpx
from streamlit.testing.v1 import AppTest

from app_paths import USER_APP_PY


@pytest.fixture(autouse=True)
def _env():
    os.environ["STREAMLIT_TEST_MODE"] = "true"
    yield


class _Resp:
    def __init__(self, ok=True, status_code=200, json_data=None, text=""):
        self.ok = ok
        self.is_success = bool(ok)
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


def test_login_success_sets_session(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/auth/token"):
            return _Resp(
                ok=True, json_data={"access_token": "tok", "token_type": "bearer"}
            )
        return _Resp(ok=True, json_data={"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)

    def fake_get(url, params=None, headers=None, timeout=None):
        if url.endswith("/users/me"):
            return _Resp(ok=True, json_data={"country": "US"})
        return _Resp(ok=True, json_data={})

    monkeypatch.setattr(httpx, "get", fake_get)

    at = AppTest.from_file(USER_APP_PY, default_timeout=30).run()
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
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/password/forgot"):
            assert json == {"email": "user@test.local"}
            return _Resp(ok=True, json_data={"ok": True})
        return _Resp(ok=False, status_code=500, text="unexpected")

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(USER_APP_PY, default_timeout=30).run()
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
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/auth/token"):
            return _Resp(
                ok=True, json_data={"access_token": "tok", "token_type": "bearer"}
            )
        return _Resp(ok=True, json_data={"ok": True})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(USER_APP_PY, default_timeout=30)
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
        or at.session_state["access_token"] is None
    )


def test_login_backend_request_exception_is_shown(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.TimeoutException("nope")

    monkeypatch.setattr(httpx, "post", boom)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(USER_APP_PY, default_timeout=30).run()
    assert not at.exception

    _text_input_by_key(at, "login_email").input("user@test.local")
    _text_input_by_key(at, "login_password").input("pw")
    _click_button(at, "Sign in")
    at.run()
    assert not at.exception

    assert len(at.error) >= 1
    assert "Backend request failed" in at.error[0].value
