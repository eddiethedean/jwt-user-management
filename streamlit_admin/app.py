import os

import requests
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from dotenv import load_dotenv
from yaml.loader import SafeLoader


load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
ADMIN_API_KEY = os.getenv("BACKEND_ADMIN_API_KEY", "")
TEST_MODE = os.getenv("STREAMLIT_TEST_MODE", "").lower() in ("1", "true", "yes")
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")


def _cookies_from_authenticator(authenticator) -> dict:
    # streamlit-authenticator exposes a cookie manager in some versions.
    if authenticator is None:
        return {}
    mgr = getattr(authenticator, "cookie_manager", None)
    if mgr is None:
        return {}
    try:
        data = mgr.get_all()
        if not data:
            return {}
        return {str(k): str(v) for k, v in dict(data).items()}
    except Exception:
        return {}


def _cookie_sig(*, authenticator=None) -> str:
    cookies = _cookies_from_authenticator(authenticator)
    items = [(k, v) for k, v in sorted(cookies.items())]
    return repr(items)


def _render_cookie_debug(*, title: str = "Cookies (debug)", authenticator=None) -> None:
    if not DEBUG:
        return
    with st.expander(title, expanded=False):
        cookies = _cookies_from_authenticator(authenticator)
        if not cookies:
            st.caption("No cookies visible to this session.")
            return
        st.json(cookies)


def _schedule_cookie_resync(*, expect: str) -> None:
    if not DEBUG:
        return
    st.session_state["_admin_cookie_sync_pending"] = True
    st.session_state["_admin_cookie_sync_attempts"] = 0
    st.session_state["_admin_cookie_sig_at_sync_start"] = st.session_state.get(
        "_admin_cookie_sig_at_sync_start"
    ) or ""
    st.session_state["_admin_cookie_expect"] = expect


def _cookie_raw(*, cookie_name: str, authenticator=None) -> str:
    raw = _cookies_from_authenticator(authenticator).get(cookie_name)
    if raw is None:
        return ""
    return str(raw)


def _cookie_expectation_met(*, expect: str, cookie_name: str, authenticator=None) -> bool:
    raw = _cookie_raw(cookie_name=cookie_name, authenticator=authenticator)
    if expect == "cleared":
        return raw == "" or raw == "deleted"
    if expect == "present":
        return raw != "" and raw != "deleted"
    return False


def _maybe_finish_cookie_resync(*, cookie_name: str, authenticator=None) -> None:
    if not st.session_state.get("_admin_cookie_sync_pending"):
        return
    expect = str(st.session_state.get("_admin_cookie_expect") or "")
    start_sig = st.session_state.get("_admin_cookie_sig_at_sync_start") or ""
    if not start_sig:
        st.session_state["_admin_cookie_sig_at_sync_start"] = _cookie_sig(
            authenticator=authenticator
        )
        start_sig = st.session_state["_admin_cookie_sig_at_sync_start"]
    cur_sig = _cookie_sig(authenticator=authenticator)

    if expect and _cookie_expectation_met(
        expect=expect, cookie_name=cookie_name, authenticator=authenticator
    ):
        st.session_state["_admin_cookie_sync_pending"] = False
        st.session_state["_admin_cookie_sync_attempts"] = 0
        st.session_state.pop("_admin_cookie_expect", None)
        return

    if not expect and cur_sig != start_sig:
        st.session_state["_admin_cookie_sync_pending"] = False
        st.session_state["_admin_cookie_sync_attempts"] = 0
        st.session_state.pop("_admin_cookie_expect", None)
        return

    attempts = int(st.session_state.get("_admin_cookie_sync_attempts") or 0) + 1
    st.session_state["_admin_cookie_sync_attempts"] = attempts
    if attempts >= 12:
        st.session_state["_admin_cookie_sync_pending"] = False
        st.session_state["_admin_cookie_sync_attempts"] = 0
        st.session_state.pop("_admin_cookie_expect", None)
        return
    st.rerun()


def backend_headers() -> dict:
    return {"X-Admin-Api-Key": ADMIN_API_KEY} if ADMIN_API_KEY else {}


def backend_get(path: str):
    try:
        return requests.get(
            f"{BACKEND_URL}{path}", headers=backend_headers(), timeout=10
        )
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


def backend_post(path: str, json: dict):
    try:
        return requests.post(
            f"{BACKEND_URL}{path}", headers=backend_headers(), json=json, timeout=10
        )
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


def backend_patch(path: str, json: dict):
    try:
        return requests.patch(
            f"{BACKEND_URL}{path}", headers=backend_headers(), json=json, timeout=10
        )
    except requests.RequestException:
        st.error("Backend request failed (is it running?)")
        return None


st.set_page_config(page_title="Admin • User Management", layout="wide")
st.title("User management")

if TEST_MODE:
    if BACKEND_URL != "http://testserver":
        st.error(
            "STREAMLIT_TEST_MODE is only allowed with BACKEND_URL=http://testserver"
        )
        st.stop()
    st.session_state["authentication_status"] = True
    st.session_state["name"] = "Test Admin"
else:
    with open("config.yaml") as file:
        config = yaml.load(file, Loader=SafeLoader)

    COOKIE_NAME = str(config["cookie"]["name"])

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )

    try:
        login_result = authenticator.login(location="main")
    except Exception as e:
        st.error(e)
        st.stop()

    if login_result is not None:
        _name, auth_ok, _username = login_result
        if auth_ok is True:
            st.session_state["_admin_cookie_sig_at_sync_start"] = _cookie_sig(
                authenticator=authenticator
            )
            _schedule_cookie_resync(expect="present")
            st.rerun()

    if "prev_authentication_status" not in st.session_state:
        st.session_state["prev_authentication_status"] = st.session_state.get(
            "authentication_status"
        )

    cur_auth = st.session_state.get("authentication_status")
    prev_auth = st.session_state.get("prev_authentication_status")
    if prev_auth is True and cur_auth is not True:
        st.session_state["_admin_cookie_sig_at_sync_start"] = _cookie_sig(
            authenticator=authenticator
        )
        _schedule_cookie_resync(expect="cleared")
        st.rerun()
    st.session_state["prev_authentication_status"] = cur_auth

_render_cookie_debug(title="Cookies (debug) • main", authenticator=locals().get("authenticator"))

if st.session_state.get("authentication_status"):
    st.sidebar.write(f"Signed in as **{st.session_state.get('name')}**")
    if not TEST_MODE:

        def _admin_logout_callback() -> None:
            st.session_state["_admin_cookie_sync_pending"] = False
            st.session_state["_admin_cookie_sync_attempts"] = 0
            st.session_state.pop("_admin_cookie_expect", None)
            st.session_state["_admin_cookie_sig_at_sync_start"] = _cookie_sig(
                authenticator=authenticator
            )
            _schedule_cookie_resync(expect="cleared")

        authenticator.logout(location="sidebar", callback=_admin_logout_callback)

    _render_cookie_debug(
        title="Cookies (debug) • sidebar", authenticator=locals().get("authenticator")
    )

    if not ADMIN_API_KEY:
        st.warning(
            "Set `BACKEND_ADMIN_API_KEY` in `streamlit_admin/.env` to enable admin API calls."
        )
        st.stop()

    col1, col2 = st.columns([2, 1], gap="large")

    with col1:
        st.subheader("Users")
        resp = backend_get("/users")
        if resp is None:
            st.stop()
        if not resp.ok:
            st.error(f"Failed to load users: {resp.status_code} {resp.text}")
        else:
            users = resp.json()
            # Avoid pandas/numpy dependency; Streamlit can render list-of-dicts directly.
            desired_keys = [
                "id",
                "email",
                "full_name",
                "is_active",
                "is_admin",
                "email_verified",
                "permissions",
                "created_at",
            ]
            rows = [
                {k: u.get(k) for k in desired_keys}
                for u in users
                if isinstance(u, dict)
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Update permissions / flags")
        user_id = st.number_input("User ID", min_value=1, step=1)
        permissions = st.text_input("Permissions (comma-separated)", value="")
        is_admin = st.checkbox("Is admin", value=False)
        is_active = st.checkbox("Is active", value=True)
        if st.button("Update user", type="primary"):
            payload = {
                "permissions": [p.strip() for p in permissions.split(",") if p.strip()],
                "is_admin": is_admin,
                "is_active": is_active,
            }
            r = backend_patch(f"/users/{int(user_id)}", json=payload)
            if r is None:
                st.stop()
            if r.ok:
                st.success("Updated")
                st.rerun()
            else:
                st.error(f"Update failed: {r.status_code} {r.text}")

    with col2:
        st.subheader("Add user (send invite email)")
        with st.form("add_user"):
            email = st.text_input("Email")
            full_name = st.text_input("Full name")
            new_is_admin = st.checkbox("Admin", value=False)
            perms = st.text_input("Permissions (comma-separated)")
            submitted = st.form_submit_button("Send invite")
        if submitted:
            payload = {
                "email": email,
                "full_name": full_name or None,
                "is_admin": new_is_admin,
                "permissions": [p.strip() for p in perms.split(",") if p.strip()],
            }
            r = backend_post("/invites", json=payload)
            if r is None:
                st.stop()
            if r.ok:
                data = r.json()
                st.success("Invite sent")
                st.code(data.get("invite_url", ""), language="text")
            else:
                st.error(f"Invite failed: {r.status_code} {r.text}")

elif st.session_state.get("authentication_status") is False:
    st.error("Username/password is incorrect")
else:
    st.warning("Please enter your username and password")

# After login/logout widgets so st.rerun() does not skip authenticator.logout / login.
if not TEST_MODE:
    _maybe_finish_cookie_resync(cookie_name=COOKIE_NAME, authenticator=authenticator)
