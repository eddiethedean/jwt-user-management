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

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )

    try:
        authenticator.login(location="main")
    except Exception as e:
        st.error(e)
        st.stop()

if st.session_state.get("authentication_status"):
    st.sidebar.write(f"Signed in as **{st.session_state.get('name')}**")
    if not TEST_MODE:
        authenticator.logout(location="sidebar")

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
