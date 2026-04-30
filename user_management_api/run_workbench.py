from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import socket
import subprocess
import webbrowser
from typing import Optional
from urllib.parse import urlparse

import uvicorn


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


def _get_root_path_for_workbench(port: int) -> str:
    """
    When running under Posit Workbench / RStudio Server, `rserver-url` returns an
    external URL (or URL prefix) for this port.
    """
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        ["/usr/lib/rstudio-server/bin/rserver-url", "-l", str(port)],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _run_migrations_if_enabled() -> None:
    """
    Ensure the DB schema is up to date for local/Workbench runs.

    Default: enabled. Disable with RUN_MIGRATIONS=0/false.
    """
    val: str = (os.environ.get("RUN_MIGRATIONS") or "").strip()
    if val and not _truthy(val):
        return
    here = Path(__file__).resolve().parent
    try:
        subprocess.check_call(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=str(here),
            env=os.environ.copy(),
        )
    except Exception as e:  # noqa: BLE001
        print("Failed to run migrations via Alembic:", e)


def start_app(
    *,
    app_module_name: str = "app.asgi",
    app_variable_name: str = "app",
    open_with_browser: bool = True,
) -> None:
    """
    Start the FastAPI app in Posit Workbench-friendly mode.

    - Picks a free ephemeral port (unless PORT is set).
    - If RS_SERVER_URL is set, uses `rserver-url` to infer the external URL/prefix.
    - Runs uvicorn with `root_path` so redirects + docs work under the proxy prefix.
    """
    host: str = os.environ.get("HOST") or "127.0.0.1"
    port: int = int(os.environ.get("PORT") or str(_free_port()))

    # Prefer explicit BASE_PATH if provided. Otherwise infer from rserver-url.
    explicit_base_path: str = (os.environ.get("BASE_PATH") or "").strip()
    root_path: str = explicit_base_path
    external_url: str = f"http://{host}:{port}"
    external_base_url: str = external_url
    external_base_is_full_url: bool = False
    external_host_url: str = ""
    parsed_netloc: Optional[str] = None
    parsed_scheme: Optional[str] = None

    if os.environ.get("RS_SERVER_URL") and not root_path:
        try:
            raw = _get_root_path_for_workbench(port)
            if raw.startswith("http://") or raw.startswith("https://"):
                external_base_url = raw.rstrip("/")
                external_base_is_full_url = True
                parsed = urlparse(external_base_url)
                parsed_scheme = parsed.scheme
                parsed_netloc = parsed.netloc
                external_host_url = f"{parsed.scheme}://{parsed.netloc}"
                root_path = parsed.path.rstrip("/")
            else:
                # Some setups may return just the path prefix.
                root_path = raw.rstrip("/")
            # Workbench may surface internal URLs with /proxy/<port>/..., but the
            # browser-reachable prefix is typically /s/<service>/p/<project>/...
            # Strip /proxy/<port> when present to avoid double-prefix redirects and
            # Swagger fetching OpenAPI from an unroutable /proxy/<port>/... path.
            m: Optional[re.Match[str]] = re.match(
                r"^/proxy/\d+(?P<rest>/.*)$", root_path
            )
            if m:
                root_path = (m.group("rest") or "").rstrip("/") or ""
                if external_base_is_full_url and parsed_scheme and parsed_netloc:
                    external_base_url = (
                        f"{parsed_scheme}://{parsed_netloc}{root_path}"
                        if root_path
                        else f"{parsed_scheme}://{parsed_netloc}"
                    )
        except Exception as e:  # noqa: BLE001
            print("Failed to retrieve root_path via rserver-url:", e)

    # If we have a Workbench external host URL, set PUBLIC_BASE_URL by default so
    # invite links are browser-routable (can be overridden explicitly).
    if external_host_url and not (os.environ.get("PUBLIC_BASE_URL") or "").strip():
        os.environ["PUBLIC_BASE_URL"] = external_host_url

    # If rserver-url returns a full external URL, it already includes the prefix.
    docs_url: str
    if external_base_is_full_url:
        docs_url = f"{external_base_url}/docs"
    else:
        docs_url = (
            f"{external_url}{root_path}/docs" if root_path else f"{external_url}/docs"
        )

    if open_with_browser:
        try:
            webbrowser.open(docs_url)
        except Exception:
            pass

    _run_migrations_if_enabled()

    uvicorn.run(
        f"{app_module_name}:{app_variable_name}",
        host=host,
        port=port,
        root_path=root_path,
        proxy_headers=True,
        forwarded_allow_ips="*",
        reload=_truthy(os.environ.get("RELOAD"))
        or bool(os.environ.get("RS_SERVER_URL")),
        log_level=os.environ.get("LOG_LEVEL") or "info",
    )


if __name__ == "__main__":
    start_app()
