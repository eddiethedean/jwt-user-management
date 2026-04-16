import os
import time
from datetime import datetime, timedelta

import extra_streamlit_components as stx
import jwt
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from typing import Dict, Optional

load_dotenv()

st.set_page_config(page_title="User App • Demo", layout="centered")
st.title("User app (demo)")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
COOKIE_NAME = os.getenv("USER_COOKIE_NAME", "user-demo-auth")
COOKIE_KEY = os.getenv("USER_COOKIE_KEY", "change-me")
COOKIE_EXPIRY_DAYS = float(os.getenv("USER_COOKIE_EXPIRY_DAYS", "7"))
DISABLE_COOKIES = os.getenv("STREAMLIT_DISABLE_COOKIES", "").lower() in (
    "1",
    "true",
    "yes",
)
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

cookie_manager = stx.CookieManager()


def _cm_key(prefix: str) -> str:
    n = int(st.session_state.get("_cm_key_counter") or 0) + 1
    st.session_state["_cm_key_counter"] = n
    return f"{prefix}_{n}"


def _cookies_from_manager() -> Dict[str, str]:
    if DISABLE_COOKIES:
        return {}
    try:
        # Keep a stable key so the component doesn't thrash.
        data = cookie_manager.get_all(key="get_all")
        if not data:
            return {}
        return {str(k): str(v) for k, v in dict(data).items()}
    except Exception:
        return {}

def _cookie_sig() -> str:
    items = [(k, v) for k, v in sorted(_cookies_from_manager().items())]
    return repr(items)


def _render_cookie_debug(*, title: str = "Cookies (debug)") -> None:
    if not DEBUG:
        return
    with st.expander(title, expanded=False):
        cookies = _cookies_from_manager()
        if not cookies:
            st.caption("No cookies visible to this session.")
            return
        st.json(cookies)


def _schedule_cookie_resync(*, expect: str) -> None:
    if not DEBUG or DISABLE_COOKIES:
        return
    st.session_state["_user_cookie_sync_pending"] = True
    st.session_state["_user_cookie_sync_attempts"] = 0
    st.session_state["_user_cookie_sig_at_sync_start"] = _cookie_sig()
    st.session_state["_user_cookie_expect"] = expect


def _cookie_raw() -> Optional[str]:
    raw = _cookies_from_manager().get(COOKIE_NAME)
    if raw is None:
        return None
    return str(raw)


def _cookie_expectation_met(expect: str) -> bool:
    raw = _cookie_raw()
    if expect == "cleared":
        return raw is None or raw == "" or raw == "deleted"
    if expect == "present":
        return raw is not None and raw != "" and raw != "deleted"
    return False


def _maybe_finish_cookie_resync() -> None:
    if not st.session_state.get("_user_cookie_sync_pending"):
        return
    expect = str(st.session_state.get("_user_cookie_expect") or "")
    start_sig = st.session_state.get("_user_cookie_sig_at_sync_start")
    cur_sig = _cookie_sig()

    # If session state already reflects the auth transition, don't let cookie lag
    # trap us in a rerun loop (which can make buttons feel unclickable).
    if expect == "cleared" and st.session_state.get("logout") and not st.session_state.get(
        "access_token"
    ):
        st.session_state["_user_cookie_sync_pending"] = False
        st.session_state["_user_cookie_sync_attempts"] = 0
        st.session_state.pop("_user_cookie_expect", None)
        return
    if expect == "present" and st.session_state.get("access_token"):
        st.session_state["_user_cookie_sync_pending"] = False
        st.session_state["_user_cookie_sync_attempts"] = 0
        st.session_state.pop("_user_cookie_expect", None)
        return

    if expect and _cookie_expectation_met(expect):
        st.session_state["_user_cookie_sync_pending"] = False
        st.session_state["_user_cookie_sync_attempts"] = 0
        st.session_state.pop("_user_cookie_expect", None)
        return

    # If we're waiting for a specific cookie state, don't bail out early just because
    # some other cookie changed (signature mismatch). Keep syncing until the expectation
    # is met (or we hit the attempt cap).
    if not expect and cur_sig != start_sig:
        st.session_state["_user_cookie_sync_pending"] = False
        st.session_state["_user_cookie_sync_attempts"] = 0
        st.session_state.pop("_user_cookie_expect", None)
        return

    attempts = int(st.session_state.get("_user_cookie_sync_attempts") or 0) + 1
    st.session_state["_user_cookie_sync_attempts"] = attempts
    if attempts >= 25:
        st.session_state["_user_cookie_sync_pending"] = False
        st.session_state["_user_cookie_sync_attempts"] = 0
        st.session_state.pop("_user_cookie_expect", None)
        return
    # Give the browser a moment to apply cookie writes/deletes before rerunning.
    time.sleep(0.05)
    st.rerun()


def _cookie_set(*, username: str, access_token: str) -> None:
    if DISABLE_COOKIES or COOKIE_EXPIRY_DAYS <= 0:
        return
    exp_date = (datetime.now() + timedelta(days=COOKIE_EXPIRY_DAYS)).timestamp()
    token = jwt.encode(
        {"username": username, "access_token": access_token, "exp_date": exp_date},
        COOKIE_KEY,
        algorithm="HS256",
    )
    cookie_manager.set(
        COOKIE_NAME,
        token,
        key=_cm_key("set"),
        path="/",
        expires_at=datetime.now() + timedelta(days=COOKIE_EXPIRY_DAYS),
    )


def _cookie_get() -> Optional[Dict]:
    if DISABLE_COOKIES:
        return None
    # Manager-only: `st.context.cookies` can lag and can make a "logged out" user
    # appear logged in again on refresh.
    raw = _cookies_from_manager().get(COOKIE_NAME)
    if raw is None and not st.session_state.get("logout"):
        # Fallback only for restore after a hard refresh when the cookie component
        # hasn't hydrated yet.
        raw = st.context.cookies.get(COOKIE_NAME)
    if not raw or raw == "deleted":
        return None
    try:
        data = jwt.decode(raw, COOKIE_KEY, algorithms=["HS256"])
    except Exception:
        return None
    exp = data.get("exp_date")
    if not exp or exp <= datetime.now().timestamp():
        return None
    return data


def _cookie_delete() -> None:
    if DISABLE_COOKIES:
        return
    # Be aggressive: different browsers / Streamlit components can behave
    # differently with delete vs overwrite+expire.
    #
    # `CookieManager.delete()` can raise KeyError if its internal cache doesn't
    # currently contain the cookie; don't let that prevent the browser-side remove.
    try:
        cookie_manager.get_all(key=_cm_key("get_all"))
    except Exception:
        pass
    try:
        cookie_manager.delete(COOKIE_NAME, key=_cm_key("delete"))
    except Exception:
        pass
    try:
        cookie_manager.set(
            COOKIE_NAME,
            "",
            key=_cm_key("set"),
            path="/",
            expires_at=datetime.now() - timedelta(days=1),
            max_age=0,
        )
        # Keep a sentinel so `_cookie_get()` won't restore even if the browser keeps
        # a value around briefly.
        cookie_manager.set(
            COOKIE_NAME,
            "deleted",
            key=_cm_key("set"),
            path="/",
            expires_at=datetime.now() - timedelta(days=1),
            max_age=0,
        )
    except Exception:
        pass

    # Extra belt-and-suspenders: force-clear via browser JS for cases where cookie
    # attributes (domain/path) prevent removal via the component.
    try:
        escaped = COOKIE_NAME.replace("'", "\\'")
        components.html(
            f"""
            <script>
              (function() {{
                var name = '{escaped}';
                var expires = 'Thu, 01 Jan 1970 00:00:00 GMT';
                var base = name + '=; expires=' + expires + '; path=/';
                document.cookie = base;
                document.cookie = base + '; SameSite=Strict';
                document.cookie = base + '; SameSite=Lax';
              }})();
            </script>
            """,
            height=0,
            width=0,
        )
    except Exception:
        pass


def _post_form(path: str, data: dict) -> Optional[requests.Response]:
    try:
        return requests.post(
            f"{BACKEND_URL}{path}",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


def _post_json(
    path: str, params: Optional[Dict] = None, json: Optional[Dict] = None
) -> Optional[requests.Response]:
    try:
        return requests.post(
            f"{BACKEND_URL}{path}", params=params, json=json, timeout=10
        )
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


def _get(path: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
    try:
        return requests.get(f"{BACKEND_URL}{path}", params=params, timeout=10)
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


def _sign_out_user() -> None:
    st.session_state.pop("access_token", None)
    st.session_state.pop("username", None)
    st.session_state["logout"] = True
    st.session_state["_user_cookie_sync_pending"] = False
    st.session_state["_user_cookie_sync_attempts"] = 0
    st.session_state.pop("_user_cookie_expect", None)
    _cookie_delete()
    _schedule_cookie_resync(expect="cleared")
    st.rerun()


# Explicit logout flag to prevent immediate cookie restore
if "logout" not in st.session_state:
    st.session_state["logout"] = False

# Restore session from cookie if present
if not st.session_state.get("logout") and "access_token" not in st.session_state:
    saved = _cookie_get()
    if saved and saved.get("access_token"):
        st.session_state["access_token"] = saved["access_token"]
        st.session_state["username"] = saved.get("username")

tab_login, tab_reset = st.tabs(["Login", "Reset password"])

with tab_login:
    _render_cookie_debug(title="Cookies (debug) • login tab")
    if st.session_state.get("access_token"):
        st.info("You're signed in. Use **Sign out** below the tabs.")
    else:
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Sign in")

        if submitted:
            resp = _post_form(
                "/auth/token", data={"username": email, "password": password}
            )
            if resp is None:
                st.stop()
            if resp.ok:
                st.session_state["access_token"] = resp.json()["access_token"]
                st.session_state["username"] = email
                st.session_state["logout"] = False
                _cookie_set(
                    username=email, access_token=st.session_state["access_token"]
                )
                _schedule_cookie_resync(expect="present")
                st.success("Signed in")
            else:
                st.error("Invalid email or password")

with tab_reset:
    _render_cookie_debug(title="Cookies (debug) • reset tab")
    st.subheader("Forgot password")
    st.caption(
        "Enter your email and we’ll send you a reset link (if the account exists)."
    )
    with st.form("forgot_form"):
        forgot_email = st.text_input("Email", key="forgot_email")
        forgot_submit = st.form_submit_button("Send reset link")

    if forgot_submit:
        resp = _post_json("/password/forgot", json={"email": forgot_email})
        if resp is None:
            st.stop()
        if resp.ok:
            st.success("If the account exists, a reset email has been sent.")
            st.info(
                f"For local dev you can open: {BACKEND_URL}/password/reset?token=<token-from-email>"
            )
        else:
            st.error(f"Reset request failed: {resp.status_code} {resp.text}")

    st.divider()
    st.subheader("Reset using token (demo)")
    st.caption(
        "If you have a reset token (from email), you can reset here without leaving Streamlit."
    )
    with st.form("reset_form"):
        token = st.text_input("Reset token", key="reset_token")
        new_password = st.text_input(
            "New password", type="password", key="reset_new_password"
        )
        reset_submit = st.form_submit_button("Reset password")

    if reset_submit:
        resp = _post_json(
            "/password/reset", json={"token": token, "password": new_password}
        )
        if resp is None:
            st.stop()
        if resp.ok:
            st.success("Password updated. You can now log in.")
        else:
            st.error(f"Reset failed: {resp.status_code} {resp.text}")

if st.session_state.get("access_token"):
    st.divider()
    st.success("Authenticated session is active.")
    if st.session_state.get("username"):
        st.caption(f"Signed in as `{st.session_state['username']}`")
    if st.button("Sign out", type="primary", key="user_sign_out_main"):
        _sign_out_user()

# Run after widgets (Sign out, forms) so st.rerun() here does not skip their handlers.
_maybe_finish_cookie_resync()
