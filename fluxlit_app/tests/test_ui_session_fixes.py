"""Unit tests for Streamlit session helpers (load_me invalidation, navigation clear)."""

from __future__ import annotations

import importlib
from unittest.mock import patch

import httpx

from ui.auth_state import SESSION_KEY, get_auth_state, logout


class _FakeSessionState(dict):
    def __getattr__(self, key: str):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def __setattr__(self, key: str, value) -> None:
        self[key] = value


class _FakeSt:
    def __init__(self) -> None:
        self.session_state = _FakeSessionState()


def test_load_me_sets_auth_invalid_on_401() -> None:
    # Other tests purge/reload ``ui.*``; bind to the current module object.
    um_profile = importlib.import_module("ui.pages.um_profile")
    um_profile = importlib.reload(um_profile)
    st = _FakeSt()

    resp = httpx.Response(401, json={"detail": "nope"})
    with patch.object(um_profile, "ApiClient") as mock_client:
        mock_client.for_fluxlit.return_value.__enter__.return_value.get.return_value = (
            resp
        )
        me = um_profile.load_me(st, "tok", session_key=SESSION_KEY)

    assert me == {}
    assert st.session_state["_auth_invalid"] is True


def test_logout_clears_navigation_state() -> None:
    import streamlit as st_mod

    fake = _FakeSessionState(
        {
            "user_auth": get_auth_state("user_auth"),
            "_page": "Admin",
            "_admin_view": "edit",
            "_edit_user_id": 3,
            "access_token": "tok",
            "username": "a@b.com",
        }
    )
    with patch.object(st_mod, "session_state", fake):
        logout(session_key="user_auth")
        assert fake["user_auth"].access_token == ""
        assert "_page" not in fake
        assert "_admin_view" not in fake
        assert "_edit_user_id" not in fake


def test_admin_back_navigation_bumps_table_gen() -> None:
    """Back/save/delete must bump dataframe key so row selection does not re-open edit."""
    um_authed = importlib.import_module("ui.pages.um_screens_authed")
    um_authed = importlib.reload(um_authed)
    st = _FakeSt()
    st.session_state["_admin_view"] = "edit"
    st.session_state["_edit_user_id"] = 5
    st.session_state["_admin_users_table_gen"] = 2

    st.session_state["_admin_view"] = "list"
    st.session_state.pop("_edit_user_id", None)
    um_authed._bump_admin_users_table(st)

    assert st.session_state["_admin_view"] == "list"
    assert "_edit_user_id" not in st.session_state
    assert st.session_state["_admin_users_table_gen"] == 3
