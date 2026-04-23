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


def _click_button(at: AppTest, label: str) -> None:
    for b in at.button:
        if getattr(b, "label", None) == label or getattr(b, "value", None) == label:
            b.click()
            return
    raise AssertionError(f"Button not found: {label}")


def _input_text(at: AppTest, label: str, value: str, occurrence: int = 0) -> None:
    matches = [t for t in at.text_input if getattr(t, "label", None) == label]
    if len(matches) <= occurrence:
        raise AssertionError(f"Text input not found: {label} (occurrence={occurrence})")
    matches[occurrence].input(value)


def test_renders_main_sections(monkeypatch):
    calls = {"users": 0}

    def fake_get(url, headers=None, timeout=None, params=None, **kwargs):
        u = url.rstrip("/")
        if u.endswith("/users/me"):
            return _Resp(
                ok=True,
                json_data={"is_admin": True, "email": "a@test.local"},
            )
        assert headers and headers.get("X-Admin-Api-Key") == "test-key"
        assert u.endswith("/users")
        calls["users"] += 1
        return _Resp(
            ok=True,
            json_data=[
                {
                    "id": 1,
                    "email": "a@test.local",
                    "full_name": "A",
                    "is_active": True,
                    "is_admin": True,
                    "email_verified": True,
                    "permissions": ["x"],
                    "created_at": "2026-01-01T00:00:00Z",
                    "ad_object_id": None,
                }
            ],
        )

    monkeypatch.setattr(requests, "get", fake_get)

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at)
    at.run()

    assert not at.exception
    assert at.title[0].value == "User management"
    assert any(s.value == "Users" for s in at.subheader)
    assert any(s.value == "Add user (send invite email)" for s in at.subheader)
    assert calls["users"] == 1

    # Clicking Refresh should trigger a rerun and re-fetch /users.
    _click_button(at, "Refresh")
    at.run()
    assert calls["users"] >= 2


def test_add_user_sends_invite(monkeypatch):
    def fake_get(url, headers=None, timeout=None, params=None, **kwargs):
        u = url.rstrip("/")
        if u.endswith("/users/me"):
            return _Resp(ok=True, json_data={"is_admin": True, "email": "a@test.local"})
        return _Resp(ok=True, json_data=[])

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "patch", lambda *a, **k: _Resp(ok=True, json_data={}))

    invite_payload = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        assert url.endswith("/invites")
        invite_payload.update(json or {})
        return _Resp(
            ok=True, json_data={"ok": True, "invite_url": "http://x/inv?token=abc"}
        )

    monkeypatch.setattr(requests, "post", fake_post)

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at)
    at.run()
    assert not at.exception

    _input_text(at, "Email", "new@test.local")
    _input_text(at, "Full name", "New Person")
    _input_text(at, "Invite permissions (comma-separated)", "p1,p2", occurrence=0)
    _click_button(at, "Send invite")
    at.run()

    assert invite_payload["email"] == "new@test.local"
    assert invite_payload["full_name"] == "New Person"
    assert invite_payload["permissions"] == ["p1", "p2"]


def test_shows_warning_when_admin_key_missing(monkeypatch):
    monkeypatch.setenv("BACKEND_ADMIN_API_KEY", "")

    def fake_get(url, headers=None, timeout=None, params=None, **kwargs):
        u = url.rstrip("/")
        if u.endswith("/users/me"):
            return _Resp(ok=True, json_data={"is_admin": True, "email": "a@test.local"})
        return _Resp(ok=True, json_data=[])

    monkeypatch.setattr(requests, "get", fake_get)

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at)
    at.run()

    assert not at.exception
    assert len(at.warning) >= 1
    assert "BACKEND_ADMIN_API_KEY" in at.warning[0].value


def test_users_endpoint_error_is_shown(monkeypatch):
    def fake_get(url, headers=None, timeout=None, params=None, **kwargs):
        u = url.rstrip("/")
        if u.endswith("/users/me"):
            return _Resp(ok=True, json_data={"is_admin": True, "email": "a@test.local"})
        return _Resp(ok=False, status_code=500, json_data={}, text="boom")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(ok=True, json_data={}))
    monkeypatch.setattr(requests, "patch", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at)
    at.run()
    assert not at.exception
    assert len(at.error) >= 1
    assert "Failed to load users" in at.error[0].value


def test_backend_request_exception_is_shown(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.Timeout("nope")

    monkeypatch.setattr(requests, "get", boom)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(ok=True, json_data={}))
    monkeypatch.setattr(requests, "patch", lambda *a, **k: _Resp(ok=True, json_data={}))

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at)
    at.run()
    assert not at.exception
    assert len(at.error) >= 1
    assert "Backend request failed" in at.error[0].value


def test_test_mode_requires_testserver_backend_url(monkeypatch):
    monkeypatch.setenv("STREAMLIT_TEST_MODE", "1")
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8000")

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30).run()
    assert not at.exception
    assert len(at.error) >= 1
    assert "STREAMLIT_TEST_MODE is only allowed" in at.error[0].value
