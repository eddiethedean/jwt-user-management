from __future__ import annotations

from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from .detect import is_workbench_request
from .urls import external_workbench_url


def _is_absolute_url(to: str) -> bool:
    try:
        p = urlparse(to)
    except Exception:
        return False
    return bool(p.scheme and p.netloc)


def _safe_relative_path(dest: str) -> str | None:
    """Return a normalized relative path or None if unsafe."""
    if not dest.startswith("/") or dest.startswith("//"):
        return None
    if _is_absolute_url(dest):
        return None
    return dest


def safe_redirect(
    request: Request,
    to: str,
    *,
    status_code: int = 303,
    prefer_relative_in_workbench: bool = True,
    public_base_url: str | None = None,
    include_root_path: bool = True,
) -> Response:
    dest = (to or "").strip() or "/"
    safe_path = _safe_relative_path(dest)
    if safe_path is None:
        safe_path = "/"

    if prefer_relative_in_workbench and is_workbench_request(request):
        return RedirectResponse(url=safe_path.lstrip("/"), status_code=status_code)
    return RedirectResponse(url=safe_path, status_code=status_code)


def safe_external_redirect(
    request: Request,
    path: str,
    *,
    status_code: int = 303,
    public_base_url: str | None = None,
    include_root_path: bool | None = None,
) -> Response:
    return RedirectResponse(
        url=external_workbench_url(
            request,
            path,
            include_root_path=include_root_path,
            public_base_url=public_base_url,
        ),
        status_code=status_code,
    )
