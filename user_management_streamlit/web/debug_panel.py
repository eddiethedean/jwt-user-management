from __future__ import annotations

from urllib.parse import quote, unquote
from typing import Any

from fastapi import Request

COOKIE_DEBUG_LOG_COOKIE = "um_cookie_debug_log"


def init_cookie_debug(request: Request, enabled: bool) -> None:
    request.state.cookie_debug_enabled = bool(enabled)
    if enabled:
        request.state.cookie_debug_logs = []
        # Bring forward the previous request's logs (useful for redirects where the
        # request that set cookies doesn't render HTML).
        prev = request.cookies.get(COOKIE_DEBUG_LOG_COOKIE)
        if prev:
            try:
                prev = unquote(prev)
            except Exception:
                prev = prev
            # Cookie may contain a compacted newline-delimited log.
            for line in prev.split("\n"):
                line_n = (line or "").strip()
                if line_n:
                    request.state.cookie_debug_logs.append(f"[prev] {line_n}")


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


def cookie_debug_payload(request: Request, *, max_chars: int = 3500) -> str:
    """
    Serialize this request's debug logs for a cookie value.

    Must stay well under typical 4KB cookie limits. We keep it plain text (no
    secrets) and trim from the front if needed.
    """
    logs = getattr(request.state, "cookie_debug_logs", None)
    if not isinstance(logs, list) or not logs:
        return ""

    # Don't store "[prev]" lines back into the cookie; we only want the latest request.
    cur = [str(x) for x in logs if isinstance(x, str) and not x.startswith("[prev] ")]
    if not cur:
        return ""

    s = "\n".join(cur)
    if len(s) <= max_chars:
        return quote(s, safe="")

    # Trim oldest lines first.
    lines = s.split("\n")
    while lines and len("\n".join(lines)) > max_chars:
        lines.pop(0)
    return quote("\n".join(lines), safe="")
