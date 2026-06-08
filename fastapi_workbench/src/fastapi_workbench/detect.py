from __future__ import annotations

import os
import re

from starlette.requests import Request
from starlette.types import Scope

_PROXY_ROOT = re.compile(r"^/proxy/\d+(?P<rest>/.*)$")


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def is_workbench_env() -> bool:
    """
    Best-effort environment detection.

    Workbench sets RS_SERVER_URL for proxied sessions. We also allow explicit
    forcing for local reproduction.
    """
    if os.environ.get("RS_SERVER_URL"):
        return True
    if _truthy(os.environ.get("WORKBENCH_FORCE")):
        return True
    return False


def is_workbench_forced() -> bool:
    """Explicit local override (``WORKBENCH_FORCE``); not implied by ``RS_SERVER_URL``."""
    return _truthy(os.environ.get("WORKBENCH_FORCE"))


def _path_has_encoded_absolute_url(path: str) -> bool:
    candidate = path.lstrip("/").lower()
    return candidate.startswith(("http%3a", "https%3a", "http://", "https://"))


def is_workbench_scope(scope: Scope) -> bool:
    """
    Scope-level heuristic for whether Workbench-like path normalization is needed.
    """
    path = str(scope.get("path") or "")
    if _path_has_encoded_absolute_url(path):
        return True

    root_path = str(scope.get("root_path") or "").rstrip("/")
    if not root_path:
        return False
    if path == root_path or path.startswith(root_path + "/"):
        return True
    m = _PROXY_ROOT.match(root_path)
    if m:
        rest = (m.group("rest") or "").rstrip("/")
        if rest and (path == rest or path.startswith(rest + "/")):
            return True
    return False


def is_workbench_request(request: Request) -> bool:
    """Per-request Workbench signals only (not bare mount or global env)."""
    return is_workbench_scope(request.scope) or is_workbench_forced()


def workbench_mode(mode: str) -> str:
    m = (mode or "").strip().lower()
    if m not in {"auto", "on", "off"}:
        raise ValueError("mode must be one of: 'auto', 'on', 'off'")
    return m


def should_normalize(*, scope: Scope, mode: str) -> bool:
    m = workbench_mode(mode)
    if m == "on":
        return True
    if m == "off":
        return False
    return is_workbench_scope(scope) or is_workbench_env()
