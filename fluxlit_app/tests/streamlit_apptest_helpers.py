"""Shared helpers for FluxLit Streamlit AppTest suites."""

from __future__ import annotations

import sys
from pathlib import Path

import fluxlit.testing as _fluxlit_testing
from streamlit.testing.v1 import AppTest

_REPO = Path(__file__).resolve().parents[2]
_FLUX = _REPO / "fluxlit_app"
FLUXLIT_MAIN = (
    Path(_fluxlit_testing.__file__).resolve().parent / "streamlit" / "main.py"
)


def setup_streamlit_paths_and_env(tmp_path, monkeypatch) -> None:
    """Autouse-style path/env prep for AppTest runs."""
    if str(_FLUX) not in sys.path:
        sys.path.insert(0, str(_FLUX))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/st.db")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    for k in ("DIRECTORY_LOOKUP_URL", "DIRECTORY_LOOKUP_REQUIRED"):
        monkeypatch.delenv(k, raising=False)
    for mod in (
        "main",
        "fluxlit_gateway",
        "api_backend",
        "paths",
        "streamlit_ui",
        "auth_state",
        "ui_helpers",
    ):
        sys.modules.pop(mod, None)
    for k in list(sys.modules.keys()):
        if k == "ui" or k.startswith("ui."):
            sys.modules.pop(k, None)


def fluxlit_env(monkeypatch) -> None:
    monkeypatch.setenv("FLUXLIT_APP", "main:app")
    monkeypatch.setenv("FLUXLIT_INTERNAL_API_BASE", "http://testserver/api")
    monkeypatch.setenv("FLUXLIT_API_PREFIX", "/api")


def text_input_by_key(at: AppTest, key: str):
    matches = [t for t in at.text_input if getattr(t, "key", None) == key]
    if not matches:
        raise AssertionError(f"Text input not found for key={key!r}")
    return matches[0]


def click_button(
    at: AppTest, *, label: str | None = None, key: str | None = None
) -> None:
    if label is None and key is None:
        raise ValueError("click_button requires label or key")
    for b in at.button:
        if key is not None and getattr(b, "key", None) == key:
            b.click()
            return
        if label is not None and (
            getattr(b, "label", None) == label or getattr(b, "value", None) == label
        ):
            b.click()
            return
    target = key or label
    raise AssertionError(f"Button not found: {target!r}")


def bridge_api_client(tc, method: str, path: str, **kwargs):
    """Delegate Streamlit ApiClient calls to a FluxLitTestClient."""
    p = path if path.startswith("/") else f"/{path}"
    if method.upper() == "GET" and "/__meta" in p:
        return tc.api_get("/__meta")
    if not p.startswith(tc.api_prefix):
        p = f"{tc.api_prefix}{p}"
    return tc.api.request(method.upper(), p, **kwargs)
