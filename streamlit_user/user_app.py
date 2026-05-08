import os
import sys
from pathlib import Path
from typing import Dict, Optional, Literal
from urllib.parse import urlparse

# ruff: noqa: E402

import httpx
import ipaddress
import streamlit as st

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover

    def load_dotenv(*args, **kwargs):  # type: ignore
        return False


_here = Path(__file__).resolve()
_streamlit_dir = str(_here.parent)
_repo_root = str(_here.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _streamlit_dir not in sys.path:
    sys.path.insert(0, _streamlit_dir)

# With the paths above, `user_common` should always be importable.
from user_common.auth_state import get_auth_state, login_success, logout  # type: ignore
from user_common.backend_client import (  # type: ignore
    BackendClient,
    safe_json,
    validate_backend_url,
)
from user_common.ui import show_http_error  # type: ignore

load_dotenv()

st.set_page_config(page_title="User Management", layout="centered")
st.title("User Management")

_default_port = (os.getenv("PORT") or "8001").strip()
_default_base_path = (os.getenv("BASE_PATH") or "").rstrip("/")
_test_mode = os.getenv("STREAMLIT_TEST_MODE", "").lower() in ("1", "true", "yes")
BACKEND_URL = (
    "http://testserver"
    if _test_mode
    else f"http://localhost:{_default_port}{_default_base_path}".rstrip("/")
)
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

if "_debug_logs" not in st.session_state:
    st.session_state["_debug_logs"] = []


def _dbg(msg: str) -> None:
    if not isinstance(st.session_state.get("_debug_logs"), list):
        st.session_state["_debug_logs"] = []
    st.session_state["_debug_logs"].append(str(msg))


def _render_debug_logs() -> None:
    if not DEBUG:
        return
    with st.sidebar.expander("Debug (mounted Streamlit)", expanded=False):
        st.code("\n".join(st.session_state.get("_debug_logs") or []))


def _render_session_debug() -> None:
    if not DEBUG:
        return
    st.sidebar.caption("Session (debug)")
    a = get_auth_state(session_key="user_auth")
    st.sidebar.json({"authenticated": a.is_authenticated, "email": a.email or "(none)"})


_dbg(f"env PORT={os.getenv('PORT')!r} BASE_PATH={os.getenv('BASE_PATH')!r}")
_dbg(f"computed BACKEND_URL={BACKEND_URL!r}")


def _backend_url_diagnostics(url: str) -> None:
    """
    Emit high-signal diagnostics for BACKEND_URL safety validation failures.
    """
    try:
        p = urlparse(url)
    except Exception as e:  # pragma: no cover
        _dbg(f"urlparse failed: {e!r}")
        return
    _dbg(
        f"parsed scheme={p.scheme!r} netloc={p.netloc!r} host={p.hostname!r} port={p.port!r}"
    )
    host = p.hostname or ""
    if host.lower() in {"localhost", "testserver"}:
        _dbg("host is localhost/testserver (allowed)")
        return

    try:
        ip = ipaddress.ip_address(host)
        _dbg(
            "host is ip "
            + f"loopback={ip.is_loopback} private={ip.is_private} link_local={ip.is_link_local} reserved={ip.is_reserved}"
        )
        return
    except ValueError:
        pass

    try:
        import socket

        infos = socket.getaddrinfo(host, p.port or 443, type=socket.SOCK_STREAM)
        addrs = sorted({i[4][0] for i in infos})
        _dbg(f"resolved addrs={addrs!r}")
        for addr in addrs:
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                _dbg(f"addr not ip: {addr!r}")
                continue
            _dbg(
                f"addr={addr} loopback={ip.is_loopback} private={ip.is_private} link_local={ip.is_link_local} reserved={ip.is_reserved}"
            )
    except Exception as e:
        _dbg(f"getaddrinfo failed: {e!r}")


try:
    validate_backend_url(BACKEND_URL)
    _dbg("validate_backend_url: ok")
except ValueError as e:
    _dbg(f"validate_backend_url: error={str(e)!r}")
    _backend_url_diagnostics(BACKEND_URL)
    _render_debug_logs()
    st.error(str(e))
    st.stop()

client = BackendClient(base_url=BACKEND_URL)

# Try to discover the externally-visible base URL from the backend (when the UI
# is mounted under FastAPI behind Workbench/Connect). This avoids guessing the
# public host/prefix. Fail silently so local dev isn't impacted.
if "_external_api_base" not in st.session_state:
    try:
        meta_url = f"{BACKEND_URL}/__meta"
        _dbg(f"meta fetch {meta_url!r}")
        r_meta = httpx.get(meta_url, timeout=5)
        _dbg(f"meta status={r_meta.status_code}")
        if r_meta.status_code < 300:
            j = r_meta.json()
            _dbg(f"meta json keys={sorted(list(j.keys()))!r}")
            ext_api = str(j.get("external_api_base") or "").rstrip("/")
            if ext_api:
                st.session_state["_external_api_base"] = ext_api
    except Exception:
        _dbg("meta fetch failed")

PUBLIC_API_BASE = str(st.session_state.get("_external_api_base") or BACKEND_URL).rstrip(
    "/"
)
_dbg(f"PUBLIC_API_BASE={PUBLIC_API_BASE!r}")
_render_debug_logs()

if st.session_state.pop("_sign_out_clicked", False):
    logout(session_key="user_auth")
    st.rerun()


def _post_form(path: str, data: dict) -> Optional[httpx.Response]:
    try:
        return client.post_form(path, data=data)
    except httpx.RequestError:
        st.error("Backend request failed (is it running?)")
        return None


def _post_json(
    path: str, params: Optional[Dict] = None, json: Optional[Dict] = None
) -> Optional[httpx.Response]:
    try:
        return client.post_json(path, params=params, json=json or {})
    except httpx.RequestError:
        st.error("Backend request failed (is it running?)")
        return None


auth = get_auth_state(session_key="user_auth")


AuthedPage = Literal["Users", "Admin", "Account"]
PublicPage = Literal["Login", "Register", "Accept invite", "Reset password"]


def _set_page(p: AuthedPage) -> None:
    st.session_state["_page"] = p


def _get_page() -> AuthedPage:
    p = st.session_state.get("_page")
    return p if p in ("Users", "Admin", "Account") else "Users"


def _authed_client() -> BackendClient:
    return BackendClient(base_url=BACKEND_URL, access_token=auth.access_token)


def _public_url(url: str) -> str:
    """
    Normalize a URL for display/copy so it uses the externally-visible base.

    The backend typically returns absolute links already (via PUBLIC_BASE_URL),
    but in mounted/proxied environments it’s safer to re-base same-origin URLs
    onto PUBLIC_API_BASE for a user to click/copy.
    """

    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith("/"):
        return f"{PUBLIC_API_BASE}{raw}"
    try:
        p = urlparse(raw)
    except Exception:
        return raw
    if p.scheme in {"http", "https"} and p.netloc:
        # Same-origin -> re-base.
        try:
            cur = urlparse(PUBLIC_API_BASE)
            if (
                cur.scheme in {"http", "https"}
                and cur.netloc
                and p.netloc == cur.netloc
            ):
                return f"{PUBLIC_API_BASE}{p.path or ''}" + (
                    f"?{p.query}" if p.query else ""
                )
        except Exception:
            return raw
    return raw


def _load_me() -> dict:
    me = st.session_state.get("_me")
    if isinstance(me, dict):
        return me
    try:
        r = _authed_client().get("/users/me")
    except httpx.RequestError:
        me = {}
    else:
        me = safe_json(r) if r.ok else {}
    st.session_state["_me"] = me
    return me


# One-run flash messages (survive reruns deterministically).
if st.session_state.pop("_flash_signed_in", False):
    st.success("Signed in")

# Backwards-compatible session keys used by existing tests/E2E.
if auth.is_authenticated:
    st.session_state["jwt"] = auth.access_token
    st.session_state["access_token"] = auth.access_token
    st.session_state["username"] = auth.email
else:
    st.session_state.pop("jwt", None)
    st.session_state.pop("access_token", None)
    st.session_state.pop("username", None)

_render_session_debug()


def _render_login() -> None:
    st.subheader("Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Sign in", key="login_submit"):
        resp = _post_form("/auth/token", data={"username": email, "password": password})
        if resp is None:
            st.stop()
        if resp.ok:
            data = safe_json(resp)
            access_token = str(data.get("access_token") or "")
            if not access_token:
                show_http_error("Login failed", resp)
                st.stop()
            login_success(
                access_token=access_token, email=email, session_key="user_auth"
            )
            st.session_state["_flash_signed_in"] = True
            st.session_state["_page"] = (
                "Admin" if bool(_load_me().get("is_admin")) else "Users"
            )
            st.rerun()
        else:
            show_http_error("Invalid email or password", resp)


def _render_register() -> None:
    st.subheader("Register")
    st.caption(
        "Enter your email to request an invite link. If directory lookup is enabled, it must validate your email."
    )
    reg_email = st.text_input("Email", key="register_email")
    if st.button("Request setup link", key="register_submit"):
        try:
            resp = httpx.post(
                f"{BACKEND_URL}/register",
                data={"email": reg_email},
                headers={"Accept": "application/json"},
                timeout=10,
            )
        except httpx.RequestError:
            st.error("Backend request failed (is it running?)")
            st.stop()
        if resp.ok:
            st.success("If allowed, a setup link was generated/sent.")
        else:
            show_http_error("Registration failed", resp)


def _render_accept_invite() -> None:
    st.subheader("Accept invite")
    st.caption("Set a password to activate your account.")
    invite_token = st.text_input("Invite token", key="invite_token")
    if st.button("Lookup invite", key="invite_lookup"):
        resp = _post_json("/invites/inspect", json={"token": invite_token})
        if resp is None:
            st.stop()
        if resp.ok:
            st.session_state["_invite_info"] = safe_json(resp)
        else:
            show_http_error("Invite not found", resp)
            st.session_state.pop("_invite_info", None)

    inv = st.session_state.get("_invite_info", {})
    if isinstance(inv, dict) and inv.get("email"):
        st.caption(f"Email: `{inv.get('email', '')}`")
        st.caption("This invite is tied to this email address.")

    invite_name = st.text_input("Full name (optional)", key="invite_full_name")
    invite_password = st.text_input("Password", type="password", key="invite_password")
    if st.button("Accept invite", key="invite_submit"):
        resp = _post_json(
            "/invites/accept",
            json={
                "token": invite_token,
                "password": invite_password,
                "full_name": invite_name,
            },
        )
        if resp is None:
            st.stop()
        if resp.ok:
            st.success("Invite accepted. You can now sign in.")
        else:
            show_http_error("Invite accept failed", resp)


def _render_reset_password() -> None:
    st.subheader("Forgot password")
    st.caption(
        "Enter your email and we’ll send you a reset link (if the account exists)."
    )
    forgot_email = st.text_input("Email", key="forgot_email")
    if st.button("Send reset link", key="forgot_submit"):
        resp = _post_json("/password/forgot", json={"email": forgot_email})
        if resp is None:
            st.stop()
        if resp.ok:
            st.success("If the account exists, a reset email has been sent.")
        else:
            st.error(f"Reset request failed: {resp.status_code} {resp.text}")

    st.divider()
    st.subheader("Reset password")
    st.caption("Choose a new password for your account.")
    token = st.text_input("Reset token", key="reset_token")
    if st.button("Lookup reset link", key="reset_lookup"):
        resp = _post_json("/password/inspect", json={"token": token})
        if resp is None:
            st.stop()
        if resp.ok:
            st.session_state["_reset_info"] = safe_json(resp)
        else:
            show_http_error("Reset link not found", resp)
            st.session_state.pop("_reset_info", None)

    ri = st.session_state.get("_reset_info", {})
    if isinstance(ri, dict) and ri.get("email"):
        st.caption(f"Email: `{ri.get('email', '')}`")
        st.caption("This reset link is tied to this email address.")

    new_password = st.text_input(
        "New password", type="password", key="reset_new_password"
    )
    if st.button("Reset password", key="reset_submit"):
        resp = _post_json(
            "/password/reset", json={"token": token, "password": new_password}
        )
        if resp is None:
            st.stop()
        if resp.ok:
            st.success("Password updated. You can now log in.")
        else:
            st.error(f"Reset failed: {resp.status_code} {resp.text}")


if auth.is_authenticated:
    me = _load_me()
    is_admin = bool(me.get("is_admin"))
    st.sidebar.subheader("Navigation")
    st.sidebar.button("Users", on_click=_set_page, args=("Users",))
    st.sidebar.button("Account", on_click=_set_page, args=("Account",))
    if is_admin:
        st.sidebar.button("Admin", on_click=_set_page, args=("Admin",))

    st.sidebar.divider()
    st.sidebar.link_button(
        "API docs", f"{PUBLIC_API_BASE}/docs", use_container_width=True
    )
    country = str(me.get("country") or "").strip()
    who = f"{auth.email}" + (f" ({country})" if country else "")
    st.sidebar.caption(f"Signed in as `{who}`")
    if st.sidebar.button("Sign out", type="primary", key="sign_out_sidebar"):
        st.session_state["_sign_out_clicked"] = True
        st.rerun()

    st.session_state.pop("_flash_signed_in", None)
    page = _get_page()

    if page == "Users":
        st.subheader("Users")
        if st.button("Refresh users", key="refresh_users"):
            try:
                r = _authed_client().get("/users")
            except httpx.RequestError:
                st.error("Backend request failed (is it running?)")
            else:
                if not r.ok:
                    show_http_error("Failed to load users", r)
                else:
                    data = safe_json(r)
                    rows = (
                        data.get("data") if isinstance(data.get("data"), list) else data
                    )
                    if not isinstance(rows, list):
                        rows = []
                    st.session_state["_users_cache"] = rows

        rows = st.session_state.get("_users_cache", [])
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("Click **Refresh users** to load the user list.")

    elif page == "Account":
        st.subheader("Account")
        st.caption(f"Email: `{me.get('email', '')}`")
        st.caption(f"Country: `{me.get('country', '')}`")
        with st.form("acct_name"):
            full_name = st.text_input(
                "Full name (optional)", value=str(me.get("full_name") or "")
            )
            saved = st.form_submit_button("Save")
        if saved:
            resp = _post_json("/users/me", json={"full_name": full_name})
            if resp is None:
                st.stop()
            if resp.ok:
                st.success("Saved")
                st.session_state.pop("_me", None)
                _load_me()
            else:
                show_http_error("Save failed", resp)

        st.divider()
        st.subheader("Change password")
        with st.form("acct_pw"):
            cur = st.text_input("Current password", type="password")
            new = st.text_input("New password", type="password")
            cfm = st.text_input("Confirm new password", type="password")
            ok = st.form_submit_button("Update password")
        if ok:
            resp = _post_json(
                "/users/me/password",
                json={
                    "current_password": cur,
                    "new_password": new,
                    "confirm_password": cfm,
                },
            )
            if resp is None:
                st.stop()
            if resp.ok:
                st.success("Password updated")
            else:
                show_http_error("Password update failed", resp)

    elif page == "Admin":
        if not is_admin:
            st.error("Admin required")
        else:
            st.subheader("Admin")
            with st.form("invite_form"):
                invite_email = st.text_input("Invite email")
                grant_admin = st.checkbox("Grant admin privileges", value=False)
                submit = st.form_submit_button("Create invite")
            if submit:
                with st.spinner("Looking up email…"):
                    resp = _post_json("/invites/lookup", json={"email": invite_email})
                if resp is None:
                    st.stop()
                if not resp.ok:
                    show_http_error("Could not verify email", resp)
                    st.stop()
                with st.spinner("Sending email…"):
                    r2 = _post_json(
                        "/invites",
                        json={"email": invite_email, "grant_admin": bool(grant_admin)},
                    )
                if r2 is None:
                    st.stop()
                if r2.ok:
                    j = safe_json(r2)
                    st.success("Invite created")
                    st.code(_public_url(str(j.get("invite_url") or "")))
                else:
                    show_http_error("Invite failed", r2)

            st.divider()
            st.subheader("Manage users")
            r = _authed_client().get("/users")
            rows = safe_json(r) if r.ok else {}
            users = rows.get("data") if isinstance(rows.get("data"), list) else rows
            if not isinstance(users, list):
                users = []
            options = {
                f"{u.get('email', '')} (id={u.get('id')})": u
                for u in users
                if isinstance(u, dict)
            }
            sel = st.selectbox("Select user", options=list(options.keys()))
            u = options.get(sel) if sel else None
            if isinstance(u, dict):
                st.caption(f"User id: `{u.get('id')}`")
                with st.form("edit_user"):
                    fn = st.text_input("Full name", value=str(u.get("full_name") or ""))
                    active = st.checkbox("Active", value=bool(u.get("is_active")))
                    admin_flag = st.checkbox("Admin", value=bool(u.get("is_admin")))
                    save_u = st.form_submit_button("Save user")
                if save_u:
                    rr = _authed_client().patch_json(
                        f"/admin/users/{u.get('id')}",
                        json={
                            "full_name": fn,
                            "is_active": active,
                            "is_admin": admin_flag,
                        },
                    )
                    if rr.ok:
                        st.success("Saved")
                    else:
                        show_http_error("Save failed", rr)

                del_confirm = st.checkbox("Confirm delete", value=False)
                if st.button("Delete user", disabled=not del_confirm):
                    user_id = int(u.get("id") or 0)
                    resp_del = httpx.delete(
                        f"{BACKEND_URL}/admin/users/{user_id}",
                        headers={"Authorization": f"Bearer {auth.access_token}"},
                        timeout=10,
                    )
                    if resp_del.status_code < 300:
                        st.success("Deleted")
                    else:
                        show_http_error("Delete failed", resp_del)
else:
    st.sidebar.subheader("Navigation")
    st.sidebar.link_button(
        "API docs", f"{PUBLIC_API_BASE}/docs", use_container_width=True
    )
    public_page: PublicPage = st.sidebar.radio(
        "Go to",
        options=["Login", "Register", "Accept invite", "Reset password"],
        index=0,
    )
    if st.sidebar.button("Sign out", type="primary", key="sign_out_sidebar"):
        # Keep existing test expectations: button exists and clears state.
        st.session_state["_sign_out_clicked"] = True
        st.rerun()

    if public_page == "Login":
        _render_login()
    elif public_page == "Register":
        _render_register()
    elif public_page == "Accept invite":
        _render_accept_invite()
    else:
        _render_reset_password()
