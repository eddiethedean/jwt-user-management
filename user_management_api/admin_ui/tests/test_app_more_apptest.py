import os

import pytest
import requests
from streamlit.testing.v1 import AppTest

from helpers import ADMIN_APP_PY, prime_admin_session


@pytest.fixture(autouse=True)
def _env():
    os.environ["STREAMLIT_TEST_MODE"] = "1"
    os.environ["BACKEND_URL"] = "http://testserver"
    os.environ["BACKEND_ADMIN_API_KEY"] = "test-key"
    yield


class _Resp:
    def __init__(self, ok=True, status_code=200, json_data=None, text=""):
        self.ok = ok
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data


def _input_text(at: AppTest, label: str, value: str, occurrence: int = 0) -> None:
    matches = [t for t in at.text_input if getattr(t, "label", None) == label]
    if len(matches) <= occurrence:
        raise AssertionError(f"Text input not found: {label} (occurrence={occurrence})")
    matches[occurrence].input(value)


def _set_number_input(at: AppTest, label: str, value: int) -> None:
    for n in at.number_input:
        if getattr(n, "label", None) == label:
            n.set_value(value)
            return
    raise AssertionError(f"Number input not found: {label}")


def _set_checkbox(at: AppTest, label: str, checked: bool) -> None:
    for c in at.checkbox:
        if getattr(c, "label", None) == label:
            if checked:
                c.check()
            else:
                c.uncheck()
            return
    raise AssertionError(f"Checkbox not found: {label}")


def _click_button(at: AppTest, label: str) -> None:
    for b in at.button:
        if getattr(b, "label", None) == label or getattr(b, "value", None) == label:
            b.click()
            return
    raise AssertionError(f"Button not found: {label}")


def test_update_user_calls_backend_patch(monkeypatch):
    def fake_get(url, headers=None, timeout=None, params=None, **kwargs):
        u = url.rstrip("/")
        if u.endswith("/users/me"):
            return _Resp(ok=True, json_data={"is_admin": True, "email": "a@test.local"})
        return _Resp(ok=True, json_data=[])

    monkeypatch.setattr(requests, "get", fake_get)

    seen = {}

    def fake_patch(url, headers=None, json=None, timeout=None, **kwargs):
        assert url.endswith("/users/7")
        seen["headers"] = headers or {}
        seen["json"] = json or {}
        return _Resp(ok=True, json_data={"ok": True})

    monkeypatch.setattr(requests, "patch", fake_patch)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at)
    at.run()
    assert not at.exception

    _set_number_input(at, "User ID", 7)
    _input_text(at, "Update permissions (comma-separated)", "alpha,beta", occurrence=0)
    _set_checkbox(at, "Is admin", True)
    _set_checkbox(at, "Is active", True)
    _click_button(at, "Update user")
    at.run()

    assert seen["headers"].get("X-Admin-Api-Key") == "test-key"
    assert seen["json"]["permissions"] == ["alpha", "beta"]
    assert seen["json"]["is_admin"] is True
    assert seen["json"]["is_active"] is True


def test_backend_users_error_is_displayed(monkeypatch):
    def fake_get(url, headers=None, timeout=None, params=None, **kwargs):
        u = url.rstrip("/")
        if u.endswith("/users/me"):
            return _Resp(ok=True, json_data={"is_admin": True, "email": "a@test.local"})
        return _Resp(ok=False, status_code=500, json_data={}, text="boom")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "patch", lambda *a, **k: _Resp(ok=True, json_data={}))
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at)
    at.run()
    assert not at.exception
    assert len(at.error) >= 1
    assert "Failed to load users" in at.error[0].value
