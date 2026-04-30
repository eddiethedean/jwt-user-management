from __future__ import annotations

from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from .detect import is_workbench_request
from .urls import external_url


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
) -> Response:
    """
    Redirect helper tuned for Workbench-style proxies.

    If `to` is an absolute URL, it is used as-is.

    If `to` starts with '/', we treat it as an application path:
    - In Workbench and prefer_relative_in_workbench=True: emit a relative redirect
      (strip leading '/') so Workbench doesn't rewrite to /proxy/<port>/...
    - Otherwise: emit an absolute-path redirect (Location: /...).

    If `to` is a relative path, it is used as-is.
    """
    dest = (to or "").strip()
    if not dest:
        dest = "/"

    if _is_absolute_url(dest):
        return RedirectResponse(url=dest, status_code=status_code)

    if dest.startswith("/"):
        if prefer_relative_in_workbench and is_workbench_request(request):
            return RedirectResponse(url=dest.lstrip("/"), status_code=status_code)
        return RedirectResponse(url=dest, status_code=status_code)

    return RedirectResponse(url=dest, status_code=status_code)


def safe_external_redirect(
    request: Request,
    path: str,
    *,
    status_code: int = 303,
    public_base_url: str | None = None,
    include_root_path: bool = True,
) -> Response:
    """
    Always redirect to a fully qualified external URL (browser-routable).
    """
    return RedirectResponse(
        url=external_url(
            request,
            path,
            include_root_path=include_root_path,
            public_base_url=public_base_url,
        ),
        status_code=status_code,
    )

