"""HTTP helpers for Streamlit (parity with ``streamlit_user/user_common/ui.py``)."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st
from fluxlit.client import ApiClient


def response_ok(resp: object) -> bool:
    """True for successful ``httpx.Response`` or legacy ``.ok`` / status_code."""
    if getattr(resp, "is_success", None) is not None:
        return bool(resp.is_success)
    if getattr(resp, "ok", None) is not None:
        return bool(resp.ok)
    sc = int(getattr(resp, "status_code", 0) or 0)
    return 200 <= sc < 300


def fluxlit_api_client_kwargs() -> dict[str, object]:
    if os.getenv("FLUXLIT_STREAMLIT_PROPAGATE_REQUEST_ID", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return {"propagate_request_id": True}
    return {}


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


def safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {"data": data}


def patch_json(api: ApiClient, path: str, *, json: dict) -> httpx.Response:
    p = path if path.startswith("/") else f"/{path}"
    return api.request("PATCH", p, json=json)
