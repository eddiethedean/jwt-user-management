from __future__ import annotations

import httpx
import streamlit as st


def show_http_error(prefix: str, resp: httpx.Response) -> None:
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
