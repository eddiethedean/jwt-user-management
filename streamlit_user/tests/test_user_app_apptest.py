import os
from typing import Optional

import pytest
import requests
from streamlit.testing.v1 import AppTest


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


def _input_text(
    at: AppTest, label: str, value: str, key_contains: Optional[str] = None
) -> None:
    # Match by label; if ambiguous, filter by key substring when available
    matches = [t for t in at.text_input if getattr(t, "label", None) == label]
    if key_contains:
        matches = [t for t in matches if key_contains in (getattr(t, "key", "") or "")]
    if not matches:
        raise AssertionError(f"Text input not found: {label}")
    matches[0].input(value)


def _click_button(at: AppTest, label: str) -> None:
    for b in at.button:
        if getattr(b, "label", None) == label or getattr(b, "value", None) == label:
            b.click()
            return
    raise AssertionError(f"Button not found: {label}")


def test_login_success_sets_session(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/auth/token"):
            return _Resp(
                ok=True, json_data={"access_token": "tok", "token_type": "bearer"}
            )
        return _Resp(ok=True, json_data={"ok": True})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file("app.py", default_timeout=30).run()
    assert not at.exception

    _input_text(at, "Email", "user@test.local", key_contains="login_email")
    _input_text(at, "Password", "pw", key_contains="login_password")
    _click_button(at, "Sign in")
    at.run()

    assert any("Signed in" in s.value for s in at.success)


def test_forgot_password_shows_non_enumerating_message(monkeypatch):
    def fake_post(url, data=None, headers=None, timeout=None, params=None, json=None):
        if url.endswith("/password/forgot"):
            assert json == {"email": "user@test.local"}
            return _Resp(ok=True, json_data={"ok": True})
        return _Resp(ok=False, status_code=500, text="unexpected")

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file("app.py", default_timeout=30).run()
    assert not at.exception

    # Switch to "Reset password" tab; AppTest runs all tabs but widgets exist.
    _input_text(at, "Email", "user@test.local", key_contains="forgot_email")
    _click_button(at, "Send reset link")
    at.run()

    assert any("reset email has been sent" in s.value.lower() for s in at.success)
