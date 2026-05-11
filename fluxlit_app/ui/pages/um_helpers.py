"""Debug UI and URL helpers for the user management FluxLit page."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import streamlit as st

from ui.auth_state import SESSION_KEY, get_auth_state

DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")


def dbg(msg: str) -> None:
    if not isinstance(st.session_state.get("_debug_logs"), list):
        st.session_state["_debug_logs"] = []
    st.session_state["_debug_logs"].append(str(msg))


def render_debug_logs() -> None:
    if not DEBUG:
        return
    with st.sidebar.expander("Debug (FluxLit)", expanded=False):
        st.code("\n".join(st.session_state.get("_debug_logs") or []))


def render_session_debug() -> None:
    if not DEBUG:
        return
    st.sidebar.caption("Session (debug)")
    a = get_auth_state(session_key=SESSION_KEY)
    st.sidebar.json({"authenticated": a.is_authenticated, "email": a.email or "(none)"})


def public_url(url: str, *, public_api_base: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith("/"):
        return f"{public_api_base.rstrip('/')}{raw}"
    try:
        p = urlparse(raw)
    except Exception:
        return raw
    if p.scheme in {"http", "https"} and p.netloc:
        try:
            cur = urlparse(public_api_base)
            if (
                cur.scheme in {"http", "https"}
                and cur.netloc
                and p.netloc == cur.netloc
            ):
                return f"{public_api_base.rstrip('/')}{p.path or ''}" + (
                    f"?{p.query}" if p.query else ""
                )
        except Exception:
            return raw
    return raw


def api_docs_link(public_api_base: str) -> str:
    base = (public_api_base or "").rstrip("/")
    if base:
        return f"{base}/docs"
    return "/api/docs"
