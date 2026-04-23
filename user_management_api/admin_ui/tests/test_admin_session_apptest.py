"""
Session verification: non-admin JWT or failed /users/me must clear stored auth.
"""

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


def _auth_cleared(session_state) -> bool:
    try:
        raw = session_state["admin_auth"]
    except KeyError:
        return True
    return not getattr(raw, "access_token", None)


def test_non_admin_jwt_clears_session_and_shows_signin(monkeypatch):
    def fake_get(url, headers=None, timeout=None, params=None, **kwargs):
        u = url.rstrip("/")
        if u.endswith("/users/me"):
            return _Resp(
                ok=True,
                json_data={
                    "is_admin": False,
                    "email": "user@test.local",
                },
            )
        return _Resp(ok=True, json_data=[])

    monkeypatch.setattr(requests, "get", fake_get)

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at, token="some-jwt", email="user@test.local")
    at.run()

    assert not at.exception
    assert any("Admin required" in e.value for e in at.error)
    assert _auth_cleared(at.session_state)
    assert any(s.value == "Admin sign in" for s in at.subheader)
    assert "access_token" not in at.session_state


def test_users_me_unauthorized_clears_session(monkeypatch):
    def fake_get(url, headers=None, timeout=None, params=None, **kwargs):
        u = url.rstrip("/")
        if u.endswith("/users/me"):
            return _Resp(
                ok=False, status_code=401, json_data={"detail": "Unauthorized"}
            )
        return _Resp(ok=True, json_data=[])

    monkeypatch.setattr(requests, "get", fake_get)

    at = AppTest.from_file(ADMIN_APP_PY, default_timeout=30)
    prime_admin_session(at)
    at.run()

    assert not at.exception
    assert len(at.error) >= 1
    assert "Failed to verify session" in at.error[0].value or "401" in at.error[0].value
    assert _auth_cleared(at.session_state)
    assert "access_token" not in at.session_state
