from __future__ import annotations

import requests
import streamlit as st


def show_http_error(prefix: str, resp: requests.Response) -> None:
    detail = ""
    try:
        data = resp.json()
        if isinstance(data, dict):
            detail = str(data.get("detail") or "")
    except Exception:
        detail = ""
    if detail:
        st.error(f"{prefix}: {resp.status_code} ({detail})")
    else:
        st.error(f"{prefix}: {resp.status_code}")


def show_request_exception(prefix: str, exc: Exception) -> None:
    st.error(f"{prefix}: {exc}")

