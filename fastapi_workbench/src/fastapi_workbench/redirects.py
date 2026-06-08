from __future__ import annotations

from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from .detect import is_workbench_request
from .path_safety import normalize_safe_path, workbench_relative_redirect_url
from .urls import external_workbench_url


def _is_absolute_url(to: str) -> bool:
    try:
        p = urlparse(to)
    except Exception:
        return False
    return bool(p.scheme and p.netloc)


def safe_redirect(
    request: Request,
    to: str,
    *,
    status_code: int = 303,
    prefer_relative_in_workbench: bool = True,
    public_base_url: str | None = None,
    include_root_path: bool = True,
    allow_parent_segments: bool = False,
) -> Response:
    dest = (to or "").strip() or "/"
    safe_path = normalize_safe_path(dest, allow_parent_segments=allow_parent_segments)
    if safe_path is None:
        safe_path = "/"

    if public_base_url is not None:
        inc: bool | None = None if include_root_path is True else include_root_path
        return RedirectResponse(
            url=external_workbench_url(
                request,
                safe_path,
                public_base_url=public_base_url,
                include_root_path=inc,
            ),
            status_code=status_code,
        )

    if prefer_relative_in_workbench and is_workbench_request(request):
        rel = workbench_relative_redirect_url(
            str(request.scope.get("path") or "/"), safe_path
        )
        return RedirectResponse(url=rel, status_code=status_code)

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
