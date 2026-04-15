import os

import pandas as pd
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
    return requests.get(f"{BACKEND_URL}{path}", headers=backend_headers(), timeout=10)


def backend_post(path: str, json: dict):
    return requests.post(
        f"{BACKEND_URL}{path}", headers=backend_headers(), json=json, timeout=10
    )


def backend_patch(path: str, json: dict):
    return requests.patch(
        f"{BACKEND_URL}{path}", headers=backend_headers(), json=json, timeout=10
    )


st.set_page_config(page_title="Admin • User Management", layout="wide")
st.title("User management")

if TEST_MODE:
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
            "Set `BACKEND_ADMIN_API_KEY` in `streamlit_app/.env` to enable admin API calls."
        )
        st.stop()

    col1, col2 = st.columns([2, 1], gap="large")

    with col1:
        st.subheader("Users")
        resp = backend_get("/users")
        if not resp.ok:
            st.error(f"Failed to load users: {resp.status_code} {resp.text}")
        else:
            users = resp.json()
            df = pd.DataFrame(users)
            if not df.empty:
                df = df[
                    [
                        "id",
                        "email",
                        "full_name",
                        "is_active",
                        "is_admin",
                        "email_verified",
                        "permissions",
                        "created_at",
                    ]
                ]
            st.dataframe(df, use_container_width=True, hide_index=True)

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
            if r.ok:
                st.success("Updated")
                st.rerun()
            else:
                st.error(f"Update failed: {r.status_code} {r.text}")

    with col2:
        st.subheader("Add user")
        with st.form("add_user"):
            email = st.text_input("Email")
            full_name = st.text_input("Full name")
            temp_password = st.text_input("Temporary password", value="ChangeMe123!")
            new_is_admin = st.checkbox("Admin", value=False)
            perms = st.text_input("Permissions (comma-separated)")
            submitted = st.form_submit_button("Create")
        if submitted:
            payload = {
                "email": email,
                "full_name": full_name or None,
                "password": temp_password,
                "is_admin": new_is_admin,
                "permissions": [p.strip() for p in perms.split(",") if p.strip()],
            }
            r = backend_post("/users", json=payload)
            if r.ok:
                st.success("User created")
                st.rerun()
            else:
                st.error(f"Create failed: {r.status_code} {r.text}")

        st.divider()
        st.subheader("Send invite")
        with st.form("send_invite"):
            invite_email = st.text_input("Invite email")
            invite_name = st.text_input("Invitee name (optional)")
            invite_is_admin = st.checkbox("Invite as admin", value=False)
            invite_perms = st.text_input("Invite permissions (comma-separated)")
            invite_submit = st.form_submit_button("Send invite")
        if invite_submit:
            payload = {
                "email": invite_email,
                "full_name": invite_name or None,
                "is_admin": invite_is_admin,
                "permissions": [
                    p.strip() for p in invite_perms.split(",") if p.strip()
                ],
            }
            r = backend_post("/invites", json=payload)
            if r.ok:
                data = r.json()
                st.success("Invite created")
                st.code(data.get("invite_url", ""), language="text")
            else:
                st.error(f"Invite failed: {r.status_code} {r.text}")

elif st.session_state.get("authentication_status") is False:
    st.error("Username/password is incorrect")
else:
    st.warning("Please enter your username and password")
