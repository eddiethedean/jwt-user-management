"""Load ``/users/me`` into session (cached on ``st.session_state``)."""

from __future__ import annotations

from typing import Any

import httpx
from fluxlit.client import ApiClient

from ui.http import fluxlit_api_client_kwargs, response_ok, safe_json


def load_me(st: Any, token: str) -> dict[str, Any]:
    me = st.session_state.get("_me")
    if isinstance(me, dict):
        return me
    try:
        with ApiClient.for_fluxlit(
            bearer_token=token, **fluxlit_api_client_kwargs()
        ) as api:
            r = api.get("/users/me")
    except httpx.RequestError:
        me = {}
    else:
        me = safe_json(r) if response_ok(r) else {}
    st.session_state["_me"] = me
    return me
