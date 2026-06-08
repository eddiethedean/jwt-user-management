"""JWT session state for the Streamlit UI (email + bearer token)."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass
class AuthState:
    access_token: str = ""
    email: str = ""

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)


def get_auth_state(session_key: str = "auth") -> AuthState:
    raw = st.session_state.get(session_key)
    if isinstance(raw, AuthState):
        return raw
    state = AuthState()
    st.session_state[session_key] = state
    return state


def login_success(
    *, access_token: str, email: str, session_key: str = "auth"
) -> AuthState:
    state = get_auth_state(session_key=session_key)
    state.access_token = access_token
    state.email = email
    return state


def clear_navigation_state() -> None:
    """Drop page/admin/deep-link markers so a new session starts clean."""
    for key in (
        "_page",
        "_admin_view",
        "_edit_user_id",
        "_admin_users_table_gen",
        "_invite_inspect_marker",
        "_invite_info",
        "_reset_inspect_marker",
        "_reset_info",
        "_public_link_marker",
        "invite_token",
        "reset_token",
        "authed_nav_radio",
        "public_page_nav",
    ):
        st.session_state.pop(key, None)


def logout(*, session_key: str = "auth") -> None:
    state = get_auth_state(session_key=session_key)
    state.access_token = ""
    state.email = ""
    st.session_state.pop("jwt", None)
    st.session_state.pop("access_token", None)
    st.session_state.pop("username", None)
    st.session_state.pop("_me", None)
    clear_navigation_state()


SESSION_KEY = "user_auth"
