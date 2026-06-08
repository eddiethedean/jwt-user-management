"""Unauthenticated flows matching ``user_management_api`` HTML pages."""

from __future__ import annotations

from typing import Any, Callable

import httpx

from ui.auth_state import SESSION_KEY, login_success
from ui.branding import self_registration_enabled
from ui.http import response_ok, safe_json, show_http_error


def _require_resp(st: Any, resp: httpx.Response | None) -> httpx.Response:
    if resp is None:
        st.stop()
    assert resp is not None
    return resp


def _inspect_invite(
    st: Any, *, post_json_pub: Callable[..., httpx.Response | None], token: str
) -> dict[str, Any]:
    token = (token or "").strip()
    if not token:
        return {}
    marker = f"inspect:{token}"
    if st.session_state.get("_invite_inspect_marker") == marker:
        cached = st.session_state.get("_invite_info")
        return cached if isinstance(cached, dict) else {}
    resp = post_json_pub("/invites/inspect", json={"token": token})
    if resp is None:
        return {}
    if response_ok(resp):
        info = safe_json(resp)
        st.session_state["_invite_info"] = info
        st.session_state["_invite_inspect_marker"] = marker
        return info
    st.session_state.pop("_invite_info", None)
    st.session_state.pop("_invite_inspect_marker", None)
    return {}


def _inspect_reset(
    st: Any, *, post_json_pub: Callable[..., httpx.Response | None], token: str
) -> dict[str, Any]:
    token = (token or "").strip()
    if not token:
        return {}
    marker = f"inspect:{token}"
    if st.session_state.get("_reset_inspect_marker") == marker:
        cached = st.session_state.get("_reset_info")
        return cached if isinstance(cached, dict) else {}
    resp = post_json_pub("/password/inspect", json={"token": token})
    if resp is None:
        return {}
    if response_ok(resp):
        info = safe_json(resp)
        st.session_state["_reset_info"] = info
        st.session_state["_reset_inspect_marker"] = marker
        return info
    st.session_state.pop("_reset_info", None)
    st.session_state.pop("_reset_inspect_marker", None)
    return {}


def render_login(
    st: Any,
    *,
    post_form: Callable[..., httpx.Response | None],
    post_json_pub: Callable[..., httpx.Response | None],
    load_me_fn: Callable[[str], dict[str, Any]],
    on_register: Callable[[], None] | None = None,
) -> None:
    with st.container(border=True):
        st.subheader("Sign in")
        if self_registration_enabled():
            st.markdown(
                '<p class="um-cardHint">Use the email and password from your invite or registration.</p>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<p class="um-cardHint">Use the email and password from your invite.</p>',
                unsafe_allow_html=True,
            )

        with st.form("login_form"):
            username = st.text_input(
                "Email", key="login_email", placeholder="name@example.com"
            )
            password = st.text_input("Password", type="password", key="login_password")
            submit_button = st.form_submit_button("Sign in")

        if submit_button:
            username = str(username or "").strip()
            password = str(password or "")
            resp = _require_resp(
                st,
                post_form("/auth/token", data={"username": username, "password": password}),
            )
            if response_ok(resp):
                data = safe_json(resp)
                access_token = str(data.get("access_token") or "")
                if not access_token:
                    show_http_error("Login failed", resp)
                    st.stop()
                login_success(
                    access_token=access_token,
                    email=username,
                    session_key=SESSION_KEY,
                )
                st.session_state["_flash_signed_in"] = True
                me = load_me_fn(access_token)
                st.session_state["_page"] = (
                    "Admin" if bool(me.get("is_admin")) else "Account"
                )
                st.rerun()
            else:
                show_http_error("Invalid email or password", resp)

        if self_registration_enabled() and on_register is not None:
            if st.button("Need an account? Register", key="login_go_register"):
                on_register()
                st.rerun()

        st.divider()
        with st.expander("Forgot your password?"):
            reset_email = st.text_input(
                "Email",
                key="login_reset_email",
                placeholder="name@example.com",
            )
            if st.button("Send reset link", key="login_send_reset"):
                resp = _require_resp(
                    st, post_json_pub("/password/forgot", json={"email": reset_email})
                )
                if response_ok(resp):
                    st.success("If the account exists, a reset email has been sent.")
                else:
                    show_http_error("Reset request failed", resp)


def render_register(
    st: Any,
    *,
    post_form: Callable[..., httpx.Response | None],
) -> None:
    with st.container(border=True):
        st.subheader("Register")
        st.markdown(
            '<p class="um-cardHint">Enter your email and we’ll send you a link to set your password.</p>',
            unsafe_allow_html=True,
        )
        reg_email = st.text_input(
            "Email", key="register_email", placeholder="name@example.com"
        )
        if st.button("Send setup link", key="register_submit"):
            resp = _require_resp(st, post_form("/register", data={"email": reg_email}))
            if response_ok(resp):
                st.success(
                    "If registration is available for this email, you will receive a setup link shortly."
                )
            else:
                show_http_error("Registration failed", resp)


def render_accept_invite(
    st: Any,
    *,
    post_json_pub: Callable[..., httpx.Response | None],
) -> None:
    with st.container(border=True):
        st.subheader("Accept invite")
        st.markdown(
            '<p class="um-cardHint">Set a password to activate your account.</p>',
            unsafe_allow_html=True,
        )

        invite_token = st.text_input("Invite token", key="invite_token")
        inv = _inspect_invite(st, post_json_pub=post_json_pub, token=invite_token)
        invite_email = str(inv.get("email") or "")
        if invite_email:
            st.text_input(
                "Email",
                value=invite_email,
                disabled=True,
                key="invite_email_readonly",
            )
            st.markdown(
                '<p class="um-cardHint">This invite is tied to this email address.</p>',
                unsafe_allow_html=True,
            )
        elif (invite_token or "").strip():
            st.warning("Invite not found or expired.")

        invite_name = st.text_input(
            "Full name (optional)", key="invite_full_name", placeholder="Jane Doe"
        )
        invite_password = st.text_input("Password", type="password", key="invite_password")
        if st.button("Set password", key="invite_submit"):
            resp = _require_resp(
                st,
                post_json_pub(
                    "/invites/accept",
                    json={
                        "token": invite_token,
                        "password": invite_password,
                        "full_name": invite_name,
                    },
                ),
            )
            if response_ok(resp):
                st.success("Invite accepted. You can now sign in.")
            else:
                show_http_error("Invite accept failed", resp)


def render_reset_password(
    st: Any,
    *,
    post_json_pub: Callable[..., httpx.Response | None],
) -> None:
    """Token-based reset page (``/password/reset`` HTML equivalent)."""
    with st.container(border=True):
        st.subheader("Reset password")
        st.markdown(
            '<p class="um-cardHint">Choose a new password for your account.</p>',
            unsafe_allow_html=True,
        )

        token = st.text_input("Reset token", key="reset_token")
        ri = _inspect_reset(st, post_json_pub=post_json_pub, token=token)
        reset_email = str(ri.get("email") or "")
        if reset_email:
            st.text_input(
                "Email",
                value=reset_email,
                disabled=True,
                key="reset_email_readonly",
            )
        elif (token or "").strip():
            st.warning("Reset link not found or expired.")

        new_password = st.text_input(
            "New password", type="password", key="reset_new_password"
        )
        if st.button("Update password", key="reset_submit"):
            resp = _require_resp(
                st,
                post_json_pub(
                    "/password/reset", json={"token": token, "password": new_password}
                ),
            )
            if response_ok(resp):
                st.success("Password updated. You can now sign in.")
            else:
                show_http_error("Reset failed", resp)
