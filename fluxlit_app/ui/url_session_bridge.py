"""FluxLit URL session continuity (``fluxlit_sid`` + :class:`InMemorySessionStore`)."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from fluxlit.config import JsonValue
from fluxlit.url_session import (
    InMemorySessionStore,
    SessionStore,
    ensure_url_session,
    hydrate_url_session,
)


def url_session_enabled() -> bool:
    return os.getenv("FLUXLIT_DISABLE_URL_SESSION", "").strip() == ""


def get_url_store(st: Any) -> InMemorySessionStore:
    key = "_fluxlit_url_session_store"
    if key not in st.session_state:
        st.session_state[key] = InMemorySessionStore()
    store = st.session_state[key]
    if not isinstance(store, InMemorySessionStore):
        store = InMemorySessionStore()
        st.session_state[key] = store
    return store


def _query_sid(st: Any, param: str = "fluxlit_sid") -> str | None:
    qp = st.query_params
    if qp is None:
        return None
    raw: Any
    try:
        raw = qp.get(param) if hasattr(qp, "get") else qp[param]
    except Exception:
        return None
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


def clear_url_session(st: Any, store: SessionStore, param: str = "fluxlit_sid") -> None:
    sid = _query_sid(st, param)
    if sid:
        store.delete(sid)
    try:
        if param in st.query_params:
            del st.query_params[param]
    except Exception:
        pass


def apply_hydrated_auth(
    st: Any,
    *,
    session_key: str,
    login_success: Callable[..., Any],
) -> None:
    token = st.session_state.get("access_token")
    email = str(st.session_state.get("username") or "")
    if token and email:
        login_success(access_token=str(token), email=email, session_key=session_key)


def narrow_session_blob(st: Any, auth: Any) -> dict[str, JsonValue]:
    out: dict[str, JsonValue] = {}
    tok = getattr(auth, "access_token", "") or ""
    if tok:
        out["access_token"] = str(tok)
    em = getattr(auth, "email", "") or ""
    if em:
        out["username"] = str(em)
    page = st.session_state.get("_page")
    if page in ("Users", "Admin", "Account"):
        out["_page"] = str(page)
    return out


def run_url_session_hydrate(
    st: Any, store: SessionStore, *, param: str = "fluxlit_sid"
) -> None:
    hydrate_url_session(st, store, param=param)


def run_url_session_ensure(
    st: Any, store: SessionStore, auth: Any, *, param: str = "fluxlit_sid"
) -> None:
    initial: dict[str, JsonValue] | None = (
        narrow_session_blob(st, auth)
        if getattr(auth, "is_authenticated", False)
        else None
    )
    ensure_url_session(st, store, param=param, initial=initial)


def persist_url_session_narrow(
    st: Any, store: SessionStore, auth: Any, *, param: str = "fluxlit_sid"
) -> None:
    sid = _query_sid(st, param)
    if not sid:
        return
    if getattr(auth, "is_authenticated", False):
        store.set(sid, narrow_session_blob(st, auth))
    else:
        store.set(sid, {})
