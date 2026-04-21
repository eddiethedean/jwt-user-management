"""Unit tests for auth helpers (Streamlit session_state is mocked)."""

from __future__ import annotations

import pytest

from streamlit_common.auth_state import (
    AuthState,
    login_success,
    logout,
    require_admin_from_me,
)


@pytest.mark.parametrize(
    "payload,expected_ok,msg_part",
    [
        ({}, False, "Admin"),
        ({"is_admin": False}, False, "Admin"),
        ({"is_admin": True}, True, None),
        ({"is_admin": 1}, True, None),
    ],
)
def test_require_admin_from_me(payload, expected_ok, msg_part):
    ok, err = require_admin_from_me(payload)
    assert ok is expected_ok
    if expected_ok:
        assert err is None
    else:
        assert err is not None and (msg_part is None or msg_part in err)


def test_login_success_updates_state(monkeypatch):
    import streamlit_common.auth_state as auth_mod

    store: dict = {}
    fake_st = type("S", (), {"session_state": store})()
    monkeypatch.setattr(auth_mod, "st", fake_st)

    st = login_success(
        access_token="jwt",
        email="a@b.c",
        session_key="k",
    )
    assert st.access_token == "jwt"
    assert st.email == "a@b.c"
    assert store["k"] is st


def test_logout_clears_auth_and_mirror_keys(monkeypatch):
    import streamlit_common.auth_state as auth_mod

    store = {
        "user_auth": AuthState(access_token="tok", email="u@x"),
        "access_token": "tok",
        "username": "u@x",
    }
    fake_st = type("S", (), {"session_state": store})()
    monkeypatch.setattr(auth_mod, "st", fake_st)

    logout(session_key="user_auth")
    assert store["user_auth"].access_token == ""
    assert store["user_auth"].email == ""
    assert "access_token" not in store
    assert "username" not in store
