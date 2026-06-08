"""Load ``/users/me`` into session (cached on ``st.session_state``)."""

from __future__ import annotations

from typing import Any

import httpx
from fluxlit.client import ApiClient

from ui.http import fluxlit_api_client_kwargs, response_ok, safe_json


def load_me(st: Any, token: str, *, session_key: str = "user_auth") -> dict[str, Any]:
    try:
        with ApiClient.for_fluxlit(
            bearer_token=token, **fluxlit_api_client_kwargs()
        ) as api:
            r = api.get("/users/me")
    except httpx.RequestError:
        me: dict[str, Any] = {}
    else:
        if r.status_code in (401, 403):
            me = {}
            st.session_state["_auth_invalid"] = True
        else:
            me = safe_json(r) if response_ok(r) else {}
    st.session_state["_me"] = me
    return me
