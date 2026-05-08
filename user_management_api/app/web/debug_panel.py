from __future__ import annotations

from typing import Any

from fastapi import Request


def init_cookie_debug(request: Request, enabled: bool) -> None:
    request.state.cookie_debug_enabled = bool(enabled)
    if enabled:
        request.state.cookie_debug_logs = []


def add_cookie_debug(request: Request, msg: str, /, **fields: Any) -> None:
    if not bool(getattr(request.state, "cookie_debug_enabled", False)):
        return

    # Keep it single-line and safe for rendering. Never log secrets here.
    line = (msg or "").strip().replace("\n", " ")
    if fields:
        parts: list[str] = []
        for k, v in fields.items():
            parts.append(f"{k}={v!r}")
        line = f"{line} | " + " ".join(parts)

    logs = getattr(request.state, "cookie_debug_logs", None)
    if isinstance(logs, list):
        logs.append(line)
