from __future__ import annotations

import os
from typing import Optional

from starlette.requests import Request
from starlette.types import Scope


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


def is_workbench_scope(scope: Scope) -> bool:
    """
    Scope-level heuristic for whether Workbench-like path normalization is needed.

    Even outside Workbench, some reverse proxies can yield a similar shape (root_path
    set and incoming path includes it). We normalize when it looks necessary.
    """
    path = str(scope.get("path") or "")

    # Encoded-absolute-URL requests should always be normalized if enabled, because
    # their path won't start with root_path until decoded.
    candidate = path.lstrip("/").lower()
    if candidate.startswith(("http%3a", "https%3a", "http://", "https://")):
        return True

    root_path = str(scope.get("root_path") or "").rstrip("/")
    if not root_path:
        return False
    if path == root_path or path.startswith(root_path + "/"):
        return True

    # Workbench sometimes sets root_path with a /proxy/<port>/... prefix but forwards
    # only a suffix of that root_path upstream. If the incoming path matches a suffix
    # of root_path, normalization is needed as well.
    rp_parts = [p for p in root_path.split("/") if p]
    for i in range(len(rp_parts)):
        suffix = "/" + "/".join(rp_parts[i:])
        if path == suffix or path.startswith(suffix + "/"):
            return True
    return False


def is_workbench_request(request: Request) -> bool:
    # After normalization, request.scope['path'] no longer includes the external
    # prefix, so is_workbench_scope() may not fire. A non-empty root_path is still a
    # strong indicator that we are operating behind a prefixing proxy (Workbench-like).
    root_path = str(request.scope.get("root_path") or "").rstrip("/")
    return bool(root_path) or is_workbench_scope(request.scope) or is_workbench_env()


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

