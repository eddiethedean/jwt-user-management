from __future__ import annotations

import logging
import os
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

LOGGER_ROOT = "user_management"

_configured = False


def _resolve_level_name(*, level: str | None, fallback: str) -> str:
    return (level or os.environ.get("LOG_LEVEL") or fallback or "info").strip().lower()


def _level_to_int(level_name: str) -> int:
    numeric = logging.getLevelName(level_name.upper())
    if isinstance(numeric, int):
        return numeric
    return logging.INFO


def configure_logging(*, level: str | None = None, fallback: str = "info") -> None:
    """Configure the application logger tree once at startup."""
    global _configured
    if _configured:
        return

    level_name = _resolve_level_name(level=level, fallback=fallback)
    numeric = _level_to_int(level_name)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root = logging.getLogger(LOGGER_ROOT)
    root.handlers.clear()
    root.setLevel(numeric)
    root.addHandler(handler)
    root.propagate = False

    _configured = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the ``user_management`` namespace."""
    if not name:
        return logging.getLogger(LOGGER_ROOT)
    if name.startswith(f"{LOGGER_ROOT}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")


def should_log_http_request(path: str) -> bool:
    """Skip noisy paths that are not useful in access logs."""
    if path.startswith("/static"):
        return False
    if path in {"/favicon.ico", "/robots.txt"}:
        return False
    return True


async def log_http_request(
    request: Request,
    call_next,
    *,
    enabled: bool = True,
) -> Response:
    """ASGI-style middleware helper: log method, path, status, and duration."""
    if not enabled:
        return await call_next(request)

    path = request.url.path
    if not should_log_http_request(path):
        return await call_next(request)

    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000.0

    access = get_logger("access")
    access.info(
        "%s %s %s %.1fms",
        request.method,
        path,
        response.status_code,
        duration_ms,
    )
    return response
