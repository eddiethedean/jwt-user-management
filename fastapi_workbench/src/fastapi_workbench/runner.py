from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
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
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        ["/usr/lib/rstudio-server/bin/rserver-url", "-l", str(port)],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _run_migrations_if_enabled(*, cwd: str | None = None) -> None:
    val: str = (os.environ.get("RUN_MIGRATIONS") or "").strip()
    if val and not _truthy(val):
        return
    try:
        subprocess.check_call(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=cwd,
            env=os.environ.copy(),
        )
    except Exception as e:  # noqa: BLE001
        print("Failed to run migrations via Alembic:", e)


def start_app(
    *,
    app_module_name: str = "app.asgi",
    app_variable_name: str = "app",
    host: str | None = None,
    port: int | None = None,
    open_with_browser: bool = True,
    migrations_cwd: str | None = None,
) -> None:
    host = host or os.environ.get("HOST") or "127.0.0.1"
    port = port or int(os.environ.get("PORT") or str(_free_port()))

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
            if raw.startswith(("http://", "https://")):
                external_base_url = raw.rstrip("/")
                external_base_is_full_url = True
                parsed = urlparse(external_base_url)
                parsed_scheme = parsed.scheme
                parsed_netloc = parsed.netloc
                external_host_url = f"{parsed.scheme}://{parsed.netloc}"
                root_path = parsed.path.rstrip("/")
            else:
                root_path = raw.rstrip("/")

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

    if external_host_url and not (os.environ.get("PUBLIC_BASE_URL") or "").strip():
        os.environ["PUBLIC_BASE_URL"] = external_host_url

    # Expose the chosen host/port and inferred prefix to child code (e.g. a UI
    # mounted inside this process) so it can build same-process URLs.
    os.environ["HOST"] = host
    os.environ["PORT"] = str(port)
    if root_path and not explicit_base_path:
        os.environ.setdefault("BASE_PATH", root_path)

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

    _run_migrations_if_enabled(cwd=migrations_cwd)

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
