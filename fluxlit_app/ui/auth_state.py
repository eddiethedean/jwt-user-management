"""Same session semantics as ``streamlit_user/user_common/auth_state.py``."""

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


def logout(*, session_key: str = "auth") -> None:
    state = get_auth_state(session_key=session_key)
    state.access_token = ""
    state.email = ""
    st.session_state.pop("jwt", None)
    st.session_state.pop("access_token", None)
    st.session_state.pop("username", None)
    st.session_state.pop("_me", None)


SESSION_KEY = "user_auth"
